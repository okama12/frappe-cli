import logging

import click

from ..utils import shell

LOG_FILE = "/var/log/frappe-installer.log"


def setup_logger():
    logger = logging.getLogger("frappe_installer.install.ssh_hardening")
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
def ssh_hardening(ctx):
    """Apply SSH security best practices (disable root login, password auth)."""
    logger.info("[ssh_hardening] Applying SSH security best practices...")
    sshd_config = "/etc/ssh/sshd_config"
    # Disable root login
    shell.run(
        ["sudo", "sed", "-i", "s/^PermitRootLogin.*/PermitRootLogin no/", sshd_config]
    )
    # Disable password authentication
    shell.run(
        [
            "sudo",
            "sed",
            "-i",
            "s/^PasswordAuthentication.*/PasswordAuthentication no/",
            sshd_config,
        ]
    )
    shell.run(["sudo", "systemctl", "restart", "ssh"])
    click.secho(
        "SSH hardening applied: root login and password auth disabled.", _fg="green"
    )
    logger.info("[ssh_hardening] SSH hardening applied.")
