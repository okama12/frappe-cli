import subprocess
import os
from typing import List, Optional, Dict, Any, Union, Tuple
from rich.console import Console
from .logging import get_logger

# Get a logger for this module
logger = get_logger("utils.shell")

def run(
    cmd: List[str],
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    sudo: bool = False,
    **kwargs: Any
) -> Optional[str]:
    """
    Run a command using subprocess.run and return its output.

    Args:
        cmd: Command to run as a list of strings
        check: Whether to check the return code
        capture_output: Whether to capture and return stdout
        text: Whether to decode output as text
        sudo: Whether to prefix the command with sudo
        **kwargs: Additional arguments to pass to subprocess.run

    Returns:
        The command output if capture_output is True, otherwise None

    Raises:
        RuntimeError: If the command fails and check is True
    """
    if sudo and cmd[0] != "sudo":
        cmd = ["sudo"] + cmd

    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=text,
            **kwargs
        )

        return result.stdout.strip() if capture_output else None

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{e.stderr}")


class RichShellRunner:
    """
    A class to run shell commands with rich output formatting.
    """

    def __init__(
        self,
        console: Console,
        dry_run: bool = False,
        debug: bool = False,
        module_name: str = "shell"
    ):
        """
        Initialize the RichShellRunner.

        Args:
            console: Rich console instance for output
            dry_run: Whether to simulate commands without executing
            debug: Whether to show debug information
            module_name: Module name for logging
        """
        self.console = console
        self.dry_run = dry_run
        self.debug = debug
        self.logger = get_logger(module_name)

    def run(
        self,
        cmd: List[str],
        description: str,
        ignore_errors: bool = False,
        capture_output: bool = False,
        **kwargs: Any
    ) -> Union[int, str, None]:
        """
        Run a command with rich output.

        Args:
            cmd: Command to run as a list of strings
            description: Human-readable description of the command
            ignore_errors: Whether to continue despite errors
            capture_output: Whether to capture and return stdout
            **kwargs: Additional arguments to pass to subprocess.run

        Returns:
            Command exit code, output string if capture_output=True, or None

        Raises:
            click.ClickException: If the command fails and ignore_errors is False
        """
        import click  # Import here to avoid circular imports

        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {' '.join(cmd)}[/dim]")

        if self.dry_run:
            self.console.print(f"[yellow][dry-run] {description}: {' '.join(cmd)}[/yellow]")
            self.logger.info(f"[dry-run] {description}: {' '.join(cmd)}")
            return 0

        self.console.print(f"[blue]{description}...[/blue]")

        try:
            if capture_output:
                # Use subprocess.run for capturing output
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    **kwargs
                )

                self.logger.info(f"Success: {description}")
                self.console.print(f"[green]✓ {description} - Complete[/green]")
                return result.stdout.strip()

            else:
                # Use subprocess.run without capturing output for better streaming
                result = subprocess.run(cmd, check=True, **kwargs)
                self.logger.info(f"Success: {description}")
                self.console.print(f"[green]✓ {description} - Complete[/green]")
                return result.returncode

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed: {' '.join(cmd)} - {e}")
            self.console.print(f"[bold red]✗ {description} failed: {e}[/bold red]")

            if not ignore_errors:
                raise click.ClickException(f"Command failed: {' '.join(cmd)}")
            else:
                self.console.print(f"[yellow]Continuing despite error...[/yellow]")
                return e.returncode

        except Exception as e:
            self.logger.error(f"Error: {' '.join(cmd)} - {e}")
            self.console.print(f"[bold red]✗ {description} error: {e}[/bold red]")

            if not ignore_errors:
                raise click.ClickException(str(e))
            else:
                self.console.print(f"[yellow]Continuing despite error...[/yellow]")
                return 1
