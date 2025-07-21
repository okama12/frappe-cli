import click
import os
import subprocess
from pathlib import Path
from rich.prompt import Prompt

from ..utils.context import create_context, CliContext
from ..utils.shell import RichShellRunner
from ..utils.logging import get_logger
from ..utils.validators import validate_not_empty
from ..utils.errors import ValidationError, CommandError

def validate_sudo(context: CliContext) -> None:
    """
    Validate that the current user has sudo access.
    
    Args:
        context: The CLI context
        
    Raises:
        click.ClickException: If sudo validation fails
    """
    context.console.print("[yellow]Validating sudo access[/yellow]")
    try:
        context.shell.run(
            cmd=["sudo", "-v"],
            description="Validating sudo access"
        )
        context.console.print("[bold green]✓ Sudo privileges validated[/bold green]")
    except Exception as e:
        context.console.print("[bold red]✗ Sudo validation failed. Please ensure you have sudo privileges.[/bold red]")
        raise click.ClickException("Sudo validation failed.")

@click.command()
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True, help='Continue installation even if some commands fail')
@click.pass_context
def bench(ctx: click.Context, dry_run: bool, debug: bool, ignore_errors: bool) -> None:
    """
    Install Frappe Bench CLI.

    Example:
        frappe install bench --debug
    """
    # Create a CLI context for this command
    context = create_context(
        module_name="install.bench",
        dry_run=dry_run,
        debug=debug,
        ignore_errors=ignore_errors
    )
    
    # Validate sudo access
    validate_sudo(context)
    
    # Get configuration from context
    config = ctx.obj.get('CONFIG', {})
    frappe_branch = config.get('frappe', {}).get('branch') or 'version-15'
    
    # Prompt for Frappe branch
    frappe_branch = Prompt.ask(
        f"Enter Frappe branch to use [default: {frappe_branch}]",
        default=frappe_branch
    )
    
    # Log the operation
    context.logger.info(f"Installing Frappe Bench (branch: {frappe_branch})...")
    context.console.print(f"[cyan]Installing Frappe Bench (branch: {frappe_branch})[/cyan]")
    
    # Ensure pipx is installed
    try:
        subprocess.run(["command", "-v", "pipx"], 
                      check=True, 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        context.logger.info("pipx is already installed")
    except subprocess.CalledProcessError:
        context.console.print("[yellow]pipx not found. Installing pipx[/yellow]")
        
        # Update package lists
        context.shell.run(
            cmd=["sudo", "apt", "update"],
            description="Updating package lists",
            ignore_errors=ignore_errors
        )
        
        # Install pipx
        context.shell.run(
            cmd=["sudo", "apt", "install", "-y", "pipx"],
            description="Installing pipx",
            ignore_errors=ignore_errors
        )
        
        # Setup pipx path
        context.shell.run(
            cmd=["pipx", "ensurepath"],
            description="Setting up pipx path",
            ignore_errors=ignore_errors
        )
    
    # Install frappe-bench using pipx
    context.shell.run(
        cmd=["pipx", "install", "--force", "frappe-bench"],
        description="Installing frappe-bench",
        ignore_errors=ignore_errors
    )
    
    # Verify installation
    try:
        subprocess.run(["command", "-v", "bench"], 
                      check=True, 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        
        # Get bench version
        version = context.shell.run(
            cmd=["bench", "--version"],
            description="Checking bench version",
            capture_output=True
        )
        
        context.logger.info(f"Bench installed successfully: {version}")
        context.console.print(f"[bold green]✓ Bench installed successfully! Version: {version}[/bold green]")
    except subprocess.CalledProcessError:
        context.logger.error("Bench installation failed - command not found")
        context.console.print("[bold red]✗ Bench installation failed - command not found[/bold red]")
        raise click.ClickException("Bench installation failed - command not found")