import click
import os
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"
LOGROTATE_CONF = "/etc/logrotate.d/frappe-installer"


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

@click.group()
def logrotate():
    """Log rotation management commands."""
    pass

@logrotate.command()
def setup():
    """Set up logrotate for /var/log/frappe-installer.log."""
    logger.info("[logrotate] Setting up logrotate for /var/log/frappe-installer.log...")
    conf_content = f"""{LOG_FILE} {{
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 640 root adm
    sharedscripts
    postrotate
        systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}}
"""
    with open("/tmp/frappe-installer-logrotate.conf", "w") as f:
        f.write(conf_content)
    shell.run(["sudo", "mv", "/tmp/frappe-installer-logrotate.conf", LOGROTATE_CONF])
    shell.run(["sudo", "chmod", "644", LOGROTATE_CONF])
    shell.run(["sudo", "logrotate", "-f", LOGROTATE_CONF])
    click.secho("Logrotate set up for /var/log/frappe-installer.log.", fg="green")
    logger.info("[logrotate] Logrotate set up for /var/log/frappe-installer.log.") 