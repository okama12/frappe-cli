import logging
import os
from typing import Optional

LOG_FILE = "/var/log/frappe-installer.log"
FALLBACK_LOG_FILE = "frappe-installer.log"

def get_logger(module_name: str) -> logging.Logger:
    """
    Get a configured logger for the specified module.
    
    Args:
        module_name: The name of the module requesting the logger
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(f"frappe_installer.{module_name}")
    logger.setLevel(logging.INFO)
    
    # Only add handler if not already present
    if not logger.handlers:
        try:
            handler = logging.FileHandler(LOG_FILE)
        except PermissionError:
            handler = logging.FileHandler(FALLBACK_LOG_FILE)
            
        formatter = logging.Formatter('[%(asctime)s] %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger