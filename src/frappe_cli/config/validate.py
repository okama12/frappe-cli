import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("config.validate")


@click.command()
def validate():
    """Validate the config file (stub)."""
    logger.info("[config] Validate called.")
    console.print(
        "[yellow][STUB] Would validate config file. Not yet implemented.[/yellow]"
    )
