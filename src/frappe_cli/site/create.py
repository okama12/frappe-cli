import click
import os
import logging
from rich.console import Console
from rich.prompt import Prompt
import getpass
from ..utils import shell

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.create")
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(LOG_FILE)
    except PermissionError:
        handler = logging.FileHandler("frappe-installer.log")
    formatter = logging.Formatter('[%(asctime)s] %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

logger = setup_logger()

class RichShell:
    def __init__(self, console, dry_run=False, debug=False):
        self.console = console
        self.dry_run = dry_run
        self.debug = debug
    def run(self, cmd, description, ignore_errors=False):
        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {' '.join(cmd)}[/dim]")
        if self.dry_run:
            self.console.print(f"[yellow][dry-run] {description}: {' '.join(cmd)}")
            logger.info(f"[dry-run] {description}: {' '.join(cmd)}")
            return 0
        self.console.print(f"[blue]{description}...[/blue]")
        try:
            result = os.system(' '.join(cmd))
            if result != 0:
                raise click.ClickException(f"Command failed: {' '.join(cmd)}")
            logger.info(f"[site] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            return result
        except Exception as e:
            logger.error(f"[site] Failed: {' '.join(cmd)} - {e}")
            self.console.print(f"[bold red]✗ {description} failed: {e}[/bold red]")
            if not ignore_errors:
                raise click.ClickException(str(e))
            else:
                self.console.print(f"[yellow]Continuing despite error...[/yellow]")
            return 1

@click.command()
@click.option('--bench-name', prompt='Enter bench name (folder)', default='frappe-bench', show_default=True, help='Bench directory name')
@click.option('--site-name', prompt='Enter site name (FQDN recommended)', default=lambda: os.uname()[1], show_default=True, help='Site name (FQDN)')
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.pass_context
def create(ctx, bench_name, site_name, dry_run, debug):
    """
    Create a new Frappe site.

    Example:
        frappe site create --bench-name mybench --site-name example.com --debug
    """
    logger.info(f"[site] Creating site: {site_name} in bench: {bench_name}")
    # Resolve bench path to user's home if not absolute
    user_home = os.path.expanduser('~')
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    if not os.path.isdir(bench_path):
        console.print(f"[bold red]Bench directory '{bench_path}' not found.[/bold red]")
        logger.error(f"[site] Bench directory '{bench_path}' not found.")
        raise click.ClickException(f"Bench directory '{bench_path}' not found.")
    os.chdir(bench_path)
    site_path = f"sites/{site_name}"
    site_config_path = os.path.join(site_path, "site_config.json")
    if os.path.isdir(site_path):
        if not os.path.isfile(site_config_path):
            console.print(f"[red]Site folder '{site_name}' exists but is incomplete (missing site_config.json).\nYou may want to delete it and try again.[/red]")
            logger.error(f"[site] Site folder '{site_name}' exists but is incomplete (missing site_config.json).")
            raise click.ClickException(f"Site folder '{site_name}' exists but is incomplete. Delete it and try again.")
        console.print(f"[yellow]Site '{site_name}' already exists. Skipping creation.[/yellow]")
        logger.info(f"[site] Site '{site_name}' already exists. Skipping.")
        return
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    shell_runner.run([
        "bench", "new-site", site_name
    ], f"Creating new site '{site_name}'", ignore_errors=ignore_errors)
    logger.info(f"[site] Site created: {site_name}")
    console.print(f"[bold green]✓ Site created: {site_name}[/bold green]")