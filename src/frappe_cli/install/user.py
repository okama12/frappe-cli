import click

from ..utils import shell
from ..utils.logging import get_logger

logger = get_logger("install.user")


@click.command()
@click.pass_context
def user(ctx):
    """Create or ensure a dedicated 'frappe' user exists."""
    config = ctx.obj.get("CONFIG", {})
    username = config.get("system", {}).get("user", "frappe")
    username = click.prompt(
        "Enter username for Frappe system user", _default=username, show_default=True
    )
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
