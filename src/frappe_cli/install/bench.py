import click
from ..utils import shell
import logging
import os

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.bench")
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
def bench(ctx):
    """Install Frappe Bench CLI."""
    config = ctx.obj.get('CONFIG', {})
    frappe_branch = config.get('frappe', {}).get('branch', 'version-15')
    frappe_branch = click.prompt('Enter Frappe branch to use', default=frappe_branch, show_default=True)
    logger.info(f"[bench] Installing Frappe Bench (branch: {frappe_branch})...")
    # Ensure pipx is installed
    if not os.system('command -v pipx > /dev/null 2>&1') == 0:
        click.echo("pipx not found. Installing pipx...")
        shell.run(["sudo", "apt", "update"])
        shell.run(["sudo", "apt", "install", "-y", "pipx"])
        shell.run(["pipx", "ensurepath"])
    # Install frappe-bench using pipx
    shell.run(["pipx", "install", "--force", "frappe-bench"])
    # Verify installation
    if not os.system('command -v bench > /dev/null 2>&1') == 0:
        logger.error("[bench] Bench installation failed - command not found")
        click.secho("Bench installation failed - command not found", fg="red")
        return
    version = shell.run(["bench", "--version"])
    logger.info(f"[bench] Bench installed successfully: {version}")
    click.secho(f"Bench installed successfully! Version: {version}", fg="green") 