import click
import os
import glob
import logging
from rich.console import Console

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.list")
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
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True, help='Continue even if some commands fail')

def list(bench_name, dry_run, debug, ignore_errors):
    """List all Frappe sites in the bench."""
    logger.info(f"[site] Listing sites in bench: {bench_name}")
    user_home = os.path.expanduser('~')
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    sites_path = os.path.join(bench_path, 'sites')
    if not os.path.isdir(sites_path):
        console.print(f"[bold red]Bench directory '{bench_path}' or sites folder not found.[/bold red]")
        logger.error(f"[site] Bench directory '{bench_path}' or sites folder not found.")
        raise click.ClickException(f"Bench directory '{bench_path}' or sites folder not found.")
    sites = [os.path.basename(d) for d in glob.glob(os.path.join(sites_path, '*')) if os.path.isdir(d) and os.path.basename(d) != 'assets']
    if not sites:
        console.print("[yellow]No sites found.[/yellow]")
        return

    console.print("[green]Sites and installed apps:[/green]")
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    for s in sites:
        site_path = os.path.join(sites_path, s)
        # Run bench command from the bench directory
        try:
            prev_cwd = os.getcwd()
            os.chdir(bench_path)
            result = os.popen(f"bench --site {s} list-apps").read().strip()
            os.chdir(prev_cwd)
            apps = result.splitlines() if result else []
        except Exception as e:
            logger.error(f"[site] Failed to run bench list-apps for site {s}: {e}")
            apps = []
        apps_str = ', '.join(apps) if apps else '[none]'
        console.print(f"- [bold]{s}[/bold]: [cyan]{apps_str}[/cyan]")
    logger.info(f"[site] Listed {len(sites)} sites and their apps in bench {bench_name}")
