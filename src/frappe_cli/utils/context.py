from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
import os
import yaml
from pathlib import Path
from rich.console import Console

from .shell import RichShellRunner
from .logging import get_logger

@dataclass
class CliContext:
    """
    Context object for CLI commands, providing access to shared resources and configuration.
    
    This class centralizes access to console, shell runner, configuration, and other
    shared resources needed by CLI commands.
    """
    # Command options
    dry_run: bool = False
    debug: bool = False
    ignore_errors: bool = False
    
    # Resources
    console: Console = field(default_factory=Console)
    config: Dict[str, Any] = field(default_factory=dict)
    module_name: str = "cli"
    
    # Lazy-loaded resources
    _shell_runner: Optional[RichShellRunner] = None
    _logger: Optional[Any] = None
    
    @property
    def shell(self) -> RichShellRunner:
        """
        Get or create a RichShellRunner instance.
        
        Returns:
            A configured RichShellRunner instance
        """
        if self._shell_runner is None:
            self._shell_runner = RichShellRunner(
                console=self.console,
                dry_run=self.dry_run,
                debug=self.debug,
                module_name=self.module_name
            )
        return self._shell_runner
    
    @property
    def logger(self) -> Any:
        """
        Get or create a logger instance.
        
        Returns:
            A configured logger instance
        """
        if self._logger is None:
            self._logger = get_logger(self.module_name)
        return self._logger
    
    def load_config(self, config_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            The loaded configuration as a dictionary
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the configuration file is invalid
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f) or {}
        
        return self.config
    
    def save_config(self, config_path: Union[str, Path]) -> None:
        """
        Save the current configuration to a YAML file.
        
        Args:
            config_path: Path to save the configuration file
            
        Raises:
            PermissionError: If the file cannot be written
        """
        config_path = Path(config_path)
        os.makedirs(config_path.parent, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)


def create_context(
    module_name: str,
    dry_run: bool = False,
    debug: bool = False,
    ignore_errors: bool = False
) -> CliContext:
    """
    Create a new CLI context with the specified options.
    
    Args:
        module_name: Name of the module for logging
        dry_run: Whether to simulate commands without executing
        debug: Whether to show debug information
        ignore_errors: Whether to continue despite errors
        
    Returns:
        A configured CliContext instance
    """
    return CliContext(
        dry_run=dry_run,
        debug=debug,
        ignore_errors=ignore_errors,
        module_name=module_name
    )