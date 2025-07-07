import click
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.system")
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
@click.pass_context
def system(ctx):
    """Update system, set timezone, install essentials."""
    config = ctx.obj.get('CONFIG', {})
    timezone = config.get('system', {}).get('timezone', 'Africa/Dar_es_Salaam')
    timezone = click.prompt('Enter timezone', default=timezone, show_default=True)
    logger.info("[system] Starting system update and setup...")
    click.echo("Updating package lists...")
    shell.run(["sudo", "apt", "update"])
    click.echo("Upgrading packages...")
    shell.run(["sudo", "DEBIAN_FRONTEND=noninteractive", "apt", "upgrade", "-y"])
    click.echo(f"Setting timezone to {timezone}...")
    shell.run(["sudo", "timedatectl", "set-timezone", timezone])
    click.echo("Installing essential packages...")
    shell.run(["sudo", "apt", "install", "-y", "curl", "wget", "git", "software-properties-common", "apt-transport-https", "ca-certificates"])
    logger.info("[system] System update and setup complete.")
    click.secho("System update and essentials installed successfully!", fg="green") 