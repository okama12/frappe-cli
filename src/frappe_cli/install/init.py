import click
from ..utils import shell
import logging
import os
from rich.console import Console
from rich.prompt import Prompt

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.init")
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

def validate_sudo():
    console.print("[yellow]Validating sudo access[/yellow]")
    result = os.system("sudo -v")
    if result != 0:
        console.print("[bold red]✗ Sudo validation failed. Please ensure you have sudo privileges.[/bold red]")
        raise click.ClickException("Sudo validation failed.")
    console.print("[bold green]✓ Sudo privileges validated[/bold green]")

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
            return
        self.console.print(f"[blue]{description}...[/blue]")
        try:
            result = os.system(' '.join(cmd))
            if result != 0:
                raise click.ClickException(f"Command failed: {' '.join(cmd)}")
            logger.info(f"[init] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            return result
        except Exception as e:
            logger.error(f"[init] Failed: {' '.join(cmd)}")
            self.console.print(f"[bold red]✗ {description} failed.[/bold red]")
            if not ignore_errors:
                raise click.ClickException(str(e))
            else:
                self.console.print(f"[yellow]Continuing despite error...[/yellow]")

@click.command()
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True, help='Continue even if some commands fail')
@click.pass_context
def init(ctx, dry_run, debug, ignore_errors):
    """Create new Frappe Bench instance."""
    validate_sudo()
    config = ctx.obj.get('CONFIG', {})
    bench_name = config.get('frappe', {}).get('bench_name') or 'frappe-bench'
    bench_name = Prompt.ask(f"Enter bench name (folder) [default: {bench_name}]", default=bench_name)
    user_home = os.path.expanduser('~')
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    frappe_branch = config.get('frappe', {}).get('branch') or 'version-15'
    frappe_branch = Prompt.ask(f"Enter Frappe branch to use [default: {frappe_branch}]", default=frappe_branch)
    logger.info(f"[init] Creating bench instance: {bench_path} (branch: {frappe_branch})")
    if os.path.isdir(bench_path):
        console.print(f"[yellow]Bench directory '{bench_path}' already exists. Skipping initialization.[/yellow]")
        logger.info(f"[init] Bench directory '{bench_path}' already exists. Skipping.")
        return
    console.print(f"[cyan]Initializing bench: {bench_path} (branch: {frappe_branch})[/cyan]")
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    shell_runner.run(["bench", "init", "--frappe-branch", frappe_branch, bench_path], "Initializing Frappe Bench", ignore_errors=ignore_errors)
    logger.info(f"[init] Bench initialized successfully: {bench_path}")
    console.print(f"[bold green]✓ Bench initialized successfully: {bench_path}[/bold green]")