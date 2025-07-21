from typing import Optional, Dict, Any, List, Union, Callable, TypeVar, cast
import os
import re
import click
from pathlib import Path

from .errors import ValidationError, ResourceNotFoundError

T = TypeVar('T')

def validate_path_exists(path: Union[str, Path], error_message: Optional[str] = None) -> Path:
    """
    Validate that a path exists.
    
    Args:
        path: The path to validate
        error_message: Custom error message if validation fails
        
    Returns:
        The validated path as a Path object
        
    Raises:
        ResourceNotFoundError: If the path doesn't exist
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise ResourceNotFoundError(
            error_message or f"Path does not exist: {path}"
        )
    return path_obj


def validate_directory_exists(path: Union[str, Path], error_message: Optional[str] = None) -> Path:
    """
    Validate that a directory exists.
    
    Args:
        path: The directory path to validate
        error_message: Custom error message if validation fails
        
    Returns:
        The validated directory path as a Path object
        
    Raises:
        ResourceNotFoundError: If the directory doesn't exist
        ValidationError: If the path exists but is not a directory
    """
    path_obj = validate_path_exists(path, error_message)
    if not path_obj.is_dir():
        raise ValidationError(
            error_message or f"Path is not a directory: {path}"
        )
    return path_obj


def validate_file_exists(path: Union[str, Path], error_message: Optional[str] = None) -> Path:
    """
    Validate that a file exists.
    
    Args:
        path: The file path to validate
        error_message: Custom error message if validation fails
        
    Returns:
        The validated file path as a Path object
        
    Raises:
        ResourceNotFoundError: If the file doesn't exist
        ValidationError: If the path exists but is not a file
    """
    path_obj = validate_path_exists(path, error_message)
    if not path_obj.is_file():
        raise ValidationError(
            error_message or f"Path is not a file: {path}"
        )
    return path_obj


def validate_sudo_access() -> None:
    """
    Validate that the current user has sudo access.
    
    Raises:
        ValidationError: If the user doesn't have sudo access
    """
    if os.geteuid() != 0:
        raise ValidationError(
            "This command requires sudo access",
            "Please run this command with sudo"
        )


def validate_pattern(value: str, pattern: str, error_message: Optional[str] = None) -> str:
    """
    Validate that a string matches a regular expression pattern.
    
    Args:
        value: The string to validate
        pattern: The regular expression pattern to match
        error_message: Custom error message if validation fails
        
    Returns:
        The validated string
        
    Raises:
        ValidationError: If the string doesn't match the pattern
    """
    if not re.match(pattern, value):
        raise ValidationError(
            error_message or f"Value '{value}' does not match pattern '{pattern}'"
        )
    return value


def validate_choice(value: T, choices: List[T], error_message: Optional[str] = None) -> T:
    """
    Validate that a value is one of the allowed choices.
    
    Args:
        value: The value to validate
        choices: The list of allowed choices
        error_message: Custom error message if validation fails
        
    Returns:
        The validated value
        
    Raises:
        ValidationError: If the value is not in the list of choices
    """
    if value not in choices:
        choices_str = ", ".join(str(c) for c in choices)
        raise ValidationError(
            error_message or f"Value '{value}' is not one of the allowed choices: {choices_str}"
        )
    return value


def validate_not_empty(value: str, error_message: Optional[str] = None) -> str:
    """
    Validate that a string is not empty.
    
    Args:
        value: The string to validate
        error_message: Custom error message if validation fails
        
    Returns:
        The validated string
        
    Raises:
        ValidationError: If the string is empty
    """
    if not value.strip():
        raise ValidationError(
            error_message or "Value cannot be empty"
        )
    return value


def click_path_exists(exists: bool = True, file_okay: bool = True, 
                     dir_okay: bool = True, readable: bool = True,
                     resolve_path: bool = True) -> Callable[[click.Context, click.Parameter, str], Path]:
    """
    Click parameter type for validating paths.
    
    Args:
        exists: Whether the path must exist
        file_okay: Whether files are allowed
        dir_okay: Whether directories are allowed
        readable: Whether the path must be readable
        resolve_path: Whether to resolve the path
        
    Returns:
        A Click parameter type function
    """
    def _validate_path(ctx: click.Context, param: click.Parameter, value: str) -> Path:
        if not value:
            return cast(Path, value)
            
        path = Path(value)
        if resolve_path:
            path = path.resolve()
            
        if exists and not path.exists():
            raise click.BadParameter(f"Path does not exist: {value}")
            
        if not file_okay and path.is_file():
            raise click.BadParameter(f"Expected directory, got file: {value}")
            
        if not dir_okay and path.is_dir():
            raise click.BadParameter(f"Expected file, got directory: {value}")
            
        if readable and path.exists() and not os.access(path, os.R_OK):
            raise click.BadParameter(f"Path is not readable: {value}")
            
        return path
        
    return _validate_path