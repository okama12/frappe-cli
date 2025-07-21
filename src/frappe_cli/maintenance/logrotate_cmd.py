import click
import os
from ..utils import shell
import logging
from rich.console import Console

LOG_FILE = "/var/log/frappe-installer.log"
LOGROTATE_CONF = "/etc/logrotate.d/frappe-installer"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.logrotate")
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

def logrotate_maintenance():
    """
    Set up logrotate for /var/log/frappe-installer.log.

    Example:
        frappe maintenance logrotate
    """
    logger.info("[logrotate] Setting up logrotate for /var/log/frappe-installer.log...")
    conf_content = f"""{LOG_FILE} {{\n    daily\n    rotate 7\n    compress\n    missingok\n    notifempty\n    create 640 root adm\n    sharedscripts\n    postrotate\n        systemctl reload rsyslog > /dev/null 2>&1 || true\n    endscript\n}}\n"""
    with open("/tmp/frappe-installer-logrotate.conf", "w") as f:
        f.write(conf_content)
    shell.run(["sudo", "mv", "/tmp/frappe-installer-logrotate.conf", LOGROTATE_CONF])
    shell.run(["sudo", "chmod", "644", LOGROTATE_CONF])
    shell.run(["sudo", "logrotate", "-f", LOGROTATE_CONF])
    console.print("[green]Logrotate set up for /var/log/frappe-installer.log.[/green]")
    logger.info("[logrotate] Logrotate set up for /var/log/frappe-installer.log.")
