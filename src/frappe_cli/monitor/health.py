import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("monitor.health")


@click.command()
def health():
    """Show system health (stub)."""
    logger.info("[monitor] Health called.")
    console.print(
        "[yellow][STUB] Would show system health. Not yet implemented.[/yellow]"
    )
