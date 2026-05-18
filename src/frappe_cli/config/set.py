import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("config.set")


@click.command()
@click.argument("key")
@click.argument("value")
def set(key, value):
    """
    Set a config value (stub).

    Example:
        frappe config set <key> <value>
    """
    logger.info(f"[config] Set called for key: {key} value: {value}")
    console.print(
        f"[yellow][STUB] Would set config key '{key}' to '{value}'. Not yet implemented.[/yellow]"
    )
