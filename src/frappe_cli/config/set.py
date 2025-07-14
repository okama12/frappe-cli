import click
import logging
from rich.console import Console

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.config.set")
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

@click.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """
    Set a config value (stub).

    Example:
        frappe config set <key> <value>
    """
    logger.info(f"[config] Set called for key: {key} value: {value}")
    console.print(f"[yellow][STUB] Would set config key '{key}' to '{value}'. Not yet implemented.[/yellow]") 