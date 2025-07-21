import logging

import click
from rich.console import Console

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()


def setup_logger():
    logger = logging.getLogger("frappe_installer.monitor.logs")
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(LOG_FILE)
    except PermissionError:
        handler = logging.FileHandler("frappe-installer.log")
    formatter = logging.Formatter("[%(asctime)s] %(message)s")
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


logger = setup_logger()


@click.command()
@click.option("--service", help="Service to tail logs for (e.g. nginx, supervisor)")
@click.option("--tail", _default=100, help="Number of log lines to show")
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
