import click

from ..utils import shell
from ..utils.logging import get_logger

logger = get_logger("install.ssh_hardening")


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
