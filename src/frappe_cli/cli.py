import click
from frappe_cli.install import install
from frappe_cli.site import site
from frappe_cli.ssl import ssl
from frappe_cli.backup import backup
from frappe_cli.service import service
from frappe_cli.firewall import firewall
from frappe_cli.app import app
from frappe_cli.rollback import rollback
from frappe_cli.maintenance import maintenance
from frappe_cli.config import config
from frappe_cli.monitor import monitor
from frappe_cli.optimize import optimize
import importlib.metadata

__version__ = importlib.metadata.version("frappe-installer")

@click.group()
@click.option('--config', type=click.Path(exists=True), help='Path to YAML config file')
@click.pass_context

def cli(ctx, config):
    """Frappe Installer CLI - Automate Frappe deployment and management.

    This CLI provides a professional interface for managing Frappe applications,
    similar to Flask CLI or Poetry. It automatically detects your Frappe environment
    and provides contextual commands.
    """
    ctx.ensure_object(dict)
    # Config loading is currently not used
    # from frappe_cli.config import load_config
    # ctx.obj['CONFIG'] = load_config(config)

@cli.command()

def version():
    """Show the Frappe CLI version."""
    click.echo(f"Frappe CLI version {__version__}")

@cli.command()

def status():
    """Show current Frappe environment status."""
    import os
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Frappe Environment Status", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Details", style="green")

    # Check if we're in a bench directory
    current_dir = os.getcwd()
    bench_detected = False
    bench_name = None

    # Look for bench in current directory or parent directories
    search_path = current_dir
    while search_path != "/" and not bench_detected:
        if os.path.exists(os.path.join(search_path, "sites")):
            bench_detected = True
            bench_name = os.path.basename(search_path)
            break
        search_path = os.path.dirname(search_path)

    if bench_detected:
        table.add_row("Bench", "✓ Found", f"{bench_name} at {search_path}")
    else:
        table.add_row("Bench", "✗ Not found", "Run 'frappe bench init' to create one")

    # Check for common services
    import subprocess
    services = ["mariadb", "redis-server", "nginx"]
    for service in services:
        try:
            result = subprocess.run(["systemctl", "is-active", service],
                                  capture_output=True, text=True, check=True)
            status = "✓ Running" if result.stdout.strip() == "active" else "⚠ Inactive"
            table.add_row(service, status, result.stdout.strip())
        except subprocess.CalledProcessError:
            table.add_row(service, "✗ Not found", "Not installed or not running")

    console.print(table)

# Add command aliases for a more natural feel
@cli.command(hidden=True)

def info():
    """Alias for 'status' command."""
    return status()

@cli.command(hidden=True)

def check():
    """Alias for 'status' command."""
    return status()

cli.add_command(install)
cli.add_command(site)
cli.add_command(ssl)
cli.add_command(backup)
cli.add_command(maintenance)
cli.add_command(service)
cli.add_command(firewall)
cli.add_command(app)
cli.add_command(rollback)

cli.add_command(config)
cli.add_command(monitor)
cli.add_command(optimize)

if __name__ == "__main__":
    cli(obj={})
