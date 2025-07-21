from typing import Optional, Dict, Any, List, Union, Type
import click

class FrappeCliError(Exception):
    """
    Base exception class for all Frappe CLI errors.

    This provides a consistent interface for error handling throughout the application.
    """
    exit_code: int = 1

    def __init__(self, message: str, details: Optional[str] = None):
        """
        Initialize a new FrappeCliError.

        Args:
            message: The main error message
            details: Optional detailed explanation or context
        """
        self.message = message
        self.details = details
        super().__init__(message)

    def format_for_console(self) -> str:
        """
        Format the error message for console output.

        Returns:
            A formatted error message string
        """
        if self.details:
            return f"{self.message}\n\nDetails: {self.details}"

        return self.message

    def to_click_exception(self) -> click.ClickException:
        """
        Convert to a Click exception for CLI error handling.

        Returns:
            A Click exception with the same message
        """
        return click.ClickException(self.format_for_console())


class ConfigurationError(FrappeCliError):
    """
    Error raised when there's an issue with configuration.
    """
    exit_code = 2


class ValidationError(FrappeCliError):
    """
    Error raised when validation fails.
    """
    exit_code = 3


class CommandError(FrappeCliError):
    """
    Error raised when a command fails.
    """
    exit_code = 4

    def __init__(self, message: str, command: Optional[List[str]] = None, details: Optional[str] = None):
        """
        Initialize a new CommandError.

        Args:
            message: The main error message
            command: The command that failed
            details: Optional detailed explanation or context
        """
        self.command = command
        super().__init__(message, details)

    def format_for_console(self) -> str:
        """
        Format the error message for console output, including the command.

        Returns:
            A formatted error message string
        """
        base_message = super().format_for_console()
        if self.command:
            return f"{base_message}\n\nCommand: {' '.join(self.command)}"

        return base_message


class PermissionError(FrappeCliError):
    """
    Error raised when permission is denied.
    """
    exit_code = 5


class ResourceNotFoundError(FrappeCliError):
    """
    Error raised when a required resource is not found.
    """
    exit_code = 6


class NetworkError(FrappeCliError):
    """
    Error raised when a network operation fails.
    """
    exit_code = 7


def handle_error(error: Exception, debug: bool = False) -> None:
    """
    Handle an exception by converting it to a Click exception and raising it.

    Args:
        error: The exception to handle
        debug: Whether to include debug information

    Raises:
        click.ClickException: Always raised with the formatted error message
    """
    if isinstance(error, FrappeCliError):
        if debug and error.details is None:
            error.details = str(error.__cause__ if error.__cause__ else "")
        raise error.to_click_exception()
    else:
        # For unexpected errors, wrap in a FrappeCliError
        message = "An unexpected error occurred"
        details = str(error) if debug else None
        wrapped_error = FrappeCliError(message, details)
        raise wrapped_error.to_click_exception()
