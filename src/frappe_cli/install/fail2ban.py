import logging

import click

from ..utils import shell

LOG_FILE = "/var/log/frappe-installer.log"


def setup_logger():
    logger = logging.getLogger("frappe_installer.install.fail2ban")
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
@click.pass_context
def fail2ban(ctx):
    """Install and enable Fail2Ban for SSH protection."""
    logger.info("[fail2ban] Installing and enabling Fail2Ban...")
    shell.run(["sudo", "apt", "install", "-y", "fail2ban"])
    shell.run(["sudo", "systemctl", "enable", "fail2ban"])
    shell.run(["sudo", "systemctl", "start", "fail2ban"])
    click.secho("Fail2Ban installed and enabled.", _fg="green")
    logger.info("[fail2ban] Fail2Ban installed and enabled.")
