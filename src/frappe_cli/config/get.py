import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("config.get")


@click.command()
@click.argument("key")
def get(key):
    """
    Get a config value (stub).

    Example:
        frappe config get <key>
    """
    logger.info(f"[config] Get called for key: {key}")
    console.print(
        f"[yellow][STUB] Would get config key '{key}'. Not yet implemented.[/yellow]"
    )
