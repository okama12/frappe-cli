import click
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"
SERVICES = ["mariadb", "redis-server", "nginx", "supervisor"]

def setup_logger():
    logger = logging.getLogger("frappe_installer.service.restart")
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
def restart():
    """Restart all relevant services (MariaDB, Redis, Nginx, Supervisor)."""
    logger.info("[service] Restarting all relevant services...")
    for svc in SERVICES:
        try:
            shell.run(["sudo", "systemctl", "restart", svc])
            click.secho(f"Restarted {svc}", fg="green")
            logger.info(f"[service] Restarted {svc}")
        except Exception as e:
            click.secho(f"Failed to restart {svc}: {e}", fg="red")
            logger.error(f"[service] Failed to restart {svc}: {e}") 