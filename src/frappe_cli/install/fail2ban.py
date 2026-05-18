import click

from ..utils import shell
from ..utils.logging import get_logger

logger = get_logger("install.fail2ban")


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
