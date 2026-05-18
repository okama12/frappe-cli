import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("monitor.logs")


@click.command()
@click.option("--service", help="Service to tail logs for (e.g. nginx, supervisor)")
@click.option("--tail", default=100, help="Number of log lines to show")
def logs(service, tail):
    """
    Show live logs for a service (stub).

    Example:
        frappe monitor logs --service nginx --tail 50
    """
    logger.info(f"[monitor] Logs called for service: {service} tail: {tail}")
    console.print(
        f"[yellow][STUB] Would show last {tail} lines of logs for service '{service}'. Not yet implemented.[/yellow]"
    )
