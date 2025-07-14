import click
import os
import logging
from rich.console import Console
from rich.prompt import Prompt
from ..utils import shell
import shutil

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.delete")
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
def delete(ctx, bench_name, site_name, dry_run, debug):
    """
    Delete a Frappe site (drops database and removes site folder).

    Example:
        frappe site delete --bench-name mybench --site-name example.com --debug
    """
    logger.info(f"[site] Deleting site: {site_name} from bench: {bench_name}")
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
    if not os.path.isdir(site_path):
        console.print(f"[yellow]Site '{site_name}' does not exist. Skipping deletion.[/yellow]")
        logger.info(f"[site] Site '{site_name}' does not exist. Skipping.")
        return
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    shell_runner.run([
        "bench", "drop-site", site_name, "--no-backup"
    ], f"Deleting site '{site_name}'", ignore_errors=ignore_errors)
    # Always try to remove the site folder in case it's left over
    if os.path.isdir(site_path):
        if dry_run:
            console.print(f"[yellow][dry-run] Would remove folder: {site_path}")
            logger.info(f"[dry-run] Would remove folder: {site_path}")
        else:
            try:
                shutil.rmtree(site_path)
                console.print(f"[green]✓ Site folder '{site_path}' removed.[/green]")
                logger.info(f"[site] Site folder '{site_path}' removed.")
            except Exception as e:
                console.print(f"[red]Failed to remove site folder '{site_path}': {e}[/red]")
                logger.error(f"[site] Failed to remove site folder '{site_path}': {e}")
    logger.info(f"[site] Site deleted: {site_name}")
    console.print(f"[bold green]✓ Site deleted: {site_name}[/bold green]") 