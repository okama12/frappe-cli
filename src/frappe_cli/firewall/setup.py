import click
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.firewall.setup")
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
def setup():
    """Configure UFW firewall for production best practices."""
    logger.info("[firewall] Configuring UFW firewall...")
    click.echo("Setting default UFW policies...")
    shell.run(["sudo", "ufw", "default", "deny", "incoming"])
    shell.run(["sudo", "ufw", "default", "allow", "outgoing"])
    click.echo("Allowing SSH (OpenSSH)...")
    shell.run(["sudo", "ufw", "allow", "OpenSSH"])
    shell.run(["sudo", "ufw", "limit", "OpenSSH"])
    click.echo("Allowing HTTP/HTTPS (Nginx Full)...")
    shell.run(["sudo", "ufw", "allow", "'Nginx Full'"])
    if click.confirm("Do you want to allow any additional custom ports/services?", default=False):
        custom_ports = click.prompt("Enter additional ports/services to allow (comma-separated, e.g. 2222/tcp,3306/tcp)", default="")
        for port in [p.strip() for p in custom_ports.split(',') if p.strip()]:
            shell.run(["sudo", "ufw", "allow", port])
            logger.info(f"[firewall] Allowed custom port/service: {port}")
    shell.run(["sudo", "ufw", "logging", "on"])
    # Warn if SSH is not allowed
    status = shell.run(["sudo", "ufw", "status"])
    if "OpenSSH" not in status:
        click.secho("Warning: SSH is not allowed in UFW rules. You may lock yourself out!", fg="red")
        logger.warning("[firewall] SSH is not allowed in UFW rules.")
    shell.run(["sudo", "ufw", "--force", "enable"])
    status = shell.run(["sudo", "ufw", "status", "verbose"])
    click.echo(f"UFW is now enabled and configured.\n\n{status}")
    logger.info(f"[firewall] UFW firewall configured.\n{status}") 