import click
import os
import logging
from rich.console import Console

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.add")
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
@click.option('--site-name', prompt='Enter site name', help='Site name to install the app on')
@click.option('--app-name', prompt='Enter app name', help='App name to install')
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True, help='Continue even if some commands fail')

def add(bench_name, site_name, app_name, dry_run, debug, ignore_errors):
    """Install a Frappe app on a site."""
    logger.info(f"[site] Installing app: {app_name} on site: {site_name} in bench: {bench_name}")
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
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    shell_runner.run([
        "bench", "--site", site_name, "install-app", app_name
    ], f"Installing app '{app_name}' on site '{site_name}'", ignore_errors=ignore_errors)
    logger.info(f"[site] App {app_name} installed on site {site_name}")
    console.print(f"[bold green]✓ App {app_name} installed on site {site_name}[/bold green]")
    # Optionally, show installed apps
    shell_runner.run([
        "bench", "--site", site_name, "list-apps"
    ], f"Listing installed apps on site '{site_name}'", ignore_errors=ignore_errors)
