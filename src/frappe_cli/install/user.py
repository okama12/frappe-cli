import click
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.user")
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

def user(ctx):
    """Create or ensure a dedicated 'frappe' user exists."""
    config = ctx.obj.get('CONFIG', {})
    username = config.get('system', {}).get('user', 'frappe')
    username = click.prompt('Enter username for Frappe system user', default=username, show_default=True)
    import pwd
    try:
        pwd.getpwnam(username)
        click.secho(f"User '{username}' already exists.", fg="yellow")
        logger.info(f"[user] User '{username}' already exists.")
    except KeyError:
        click.echo(f"Creating user '{username}'...")
        shell.run(["sudo", "useradd", "-m", "-s", "/bin/bash", username])
        shell.run(["sudo", "usermod", "-aG", "sudo", username])
        click.secho(f"User '{username}' created and added to sudo group.", fg="green")
        logger.info(f"[user] User '{username}' created and added to sudo group.")
