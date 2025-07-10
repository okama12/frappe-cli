import click
from ..utils import shell
import logging
import os
from rich.console import Console
from rich.prompt import Prompt

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.bench")
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
                raise Exception(f"Command failed: {' '.join(cmd)}")
            logger.info(f"[bench] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            return result
        except Exception as e:
            logger.error(f"[bench] Failed: {' '.join(cmd)}")
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
def bench(ctx, dry_run, debug, ignore_errors):
    """Install Frappe Bench CLI."""
    validate_sudo()
    config = ctx.obj.get('CONFIG', {})
    frappe_branch = config.get('frappe', {}).get('branch') or 'version-15'
    frappe_branch = Prompt.ask(
        f"Enter Frappe branch to use [default: {frappe_branch}]",
        default=frappe_branch
    )
    logger.info(f"[bench] Installing Frappe Bench (branch: {frappe_branch})...")
    console.print(f"[cyan]Installing Frappe Bench (branch: {frappe_branch})[/cyan]")
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    # Ensure pipx is installed
    if os.system('command -v pipx > /dev/null 2>&1') != 0:
        console.print("[yellow]pipx not found. Installing pipx[/yellow]")
        shell_runner.run(["sudo", "apt", "update"], "Updating package lists", ignore_errors=ignore_errors)
        shell_runner.run(["sudo", "apt", "install", "-y", "pipx"], "Installing pipx", ignore_errors=ignore_errors)
        shell_runner.run(["pipx", "ensurepath"], "Setting up pipx path", ignore_errors=ignore_errors)
    # Install frappe-bench using pipx
    shell_runner.run(["pipx", "install", "--force", "frappe-bench"], "Installing frappe-bench", ignore_errors=ignore_errors)
    # Verify installation
    if os.system('command -v bench > /dev/null 2>&1') != 0:
        logger.error("[bench] Bench installation failed - command not found")
        console.print("[bold red]✗ Bench installation failed - command not found[/bold red]")
        return
    version = os.popen("bench --version").read().strip()
    logger.info(f"[bench] Bench installed successfully: {version}")
    console.print(f"[bold green]✓ Bench installed successfully! Version: {version}[/bold green]")