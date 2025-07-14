import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Optional, List

console = Console()

class FrappeCLIError(click.ClickException):
    """Base exception for Frappe CLI with rich formatting."""
    
    def __init__(self, message: str, hint: Optional[str] = None, 
                 solution: Optional[str] = None, code: Optional[int] = None):
        self.message = message
        self.hint = hint
        self.solution = solution
        self.code = code
        super().__init__(message)
    
    def show(self, file=None):
        """Show the error with rich formatting."""
        # Create the error message
        error_text = Text()
        error_text.append("Error: ", style="bold red")
        error_text.append(self.message, style="red")
        
        # Add hint if provided
        if self.hint:
            error_text.append("\n\nHint: ", style="bold yellow")
            error_text.append(self.hint, style="yellow")
        
        # Add solution if provided
        if self.solution:
            error_text.append("\n\nSolution: ", style="bold green")
            error_text.append(self.solution, style="green")
        
        # Create and display the panel
        panel = Panel(
            error_text,
            title="[bold red]Frappe CLI Error[/bold red]",
            border_style="red",
            padding=(1, 2)
        )
        console.print(panel)

def handle_command_error(func):
    """Decorator to handle common command errors with professional messages."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            if "bench" in str(e).lower():
                raise FrappeCLIError(
                    "No Frappe bench found",
                    "Make sure you're in a bench directory or create one first",
                    "Run 'frappe bench init' to create a new bench"
                )
            elif "site" in str(e).lower():
                raise FrappeCLIError(
                    "Site not found",
                    "The specified site doesn't exist",
                    "Run 'frappe site list' to see available sites"
                )
            else:
                raise FrappeCLIError(f"File not found: {e}")
        except PermissionError as e:
            raise FrappeCLIError(
                "Permission denied",
                "You don't have sufficient permissions to perform this action",
                "Try running with sudo or check file permissions"
            )
        except subprocess.CalledProcessError as e:
            raise FrappeCLIError(
                f"Command failed: {e.cmd[0]}",
                f"Exit code: {e.returncode}",
                "Check the logs for more details or run with --debug flag"
            )
        except Exception as e:
            raise FrappeCLIError(f"Unexpected error: {str(e)}")
    return wrapper

def print_success(message: str, details: Optional[str] = None):
    """Print a success message with rich formatting."""
    success_text = Text()
    success_text.append("✓ ", style="bold green")
    success_text.append(message, style="green")
    
    if details:
        success_text.append(f"\n{details}", style="dim")
    
    panel = Panel(
        success_text,
        title="[bold green]Success[/bold green]",
        border_style="green",
        padding=(1, 2)
    )
    console.print(panel)

def print_warning(message: str, details: Optional[str] = None):
    """Print a warning message with rich formatting."""
    warning_text = Text()
    warning_text.append("⚠ ", style="bold yellow")
    warning_text.append(message, style="yellow")
    
    if details:
        warning_text.append(f"\n{details}", style="dim")
    
    panel = Panel(
        warning_text,
        title="[bold yellow]Warning[/bold yellow]",
        border_style="yellow",
        padding=(1, 2)
    )
    console.print(panel)

def print_info(message: str, details: Optional[str] = None):
    """Print an info message with rich formatting."""
    info_text = Text()
    info_text.append("ℹ ", style="bold blue")
    info_text.append(message, style="blue")
    
    if details:
        info_text.append(f"\n{details}", style="dim")
    
    panel = Panel(
        info_text,
        title="[bold blue]Info[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(panel) 