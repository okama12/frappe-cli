import click
from ..utils import shell
import logging
from rich.console import Console

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

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
    """
    Configure UFW firewall for production best practices.

    Example:
        frappe firewall setup
    """
    logger.info("[firewall] Configuring UFW firewall...")
    console.print("[blue]Setting default UFW policies...[/blue]")
    shell.run(["sudo", "ufw", "default", "deny", "incoming"])
    shell.run(["sudo", "ufw", "default", "allow", "outgoing"])
    console.print("[blue]Allowing SSH (OpenSSH)...[/blue]")
    shell.run(["sudo", "ufw", "allow", "OpenSSH"])
    shell.run(["sudo", "ufw", "limit", "OpenSSH"])
    console.print("[blue]Allowing HTTP/HTTPS (Nginx Full)...[/blue]")
    shell.run(["sudo", "ufw", "allow", "'Nginx Full'"])
    if click.confirm("Do you want to allow any additional custom ports/services?", default=False):
        custom_ports = click.prompt("Enter additional ports/services to allow (comma-separated, e.g. 2222/tcp,3306/tcp)", default="")
        for port in [p.strip() for p in custom_ports.split(',') if p.strip()]:
            shell.run(["sudo", "ufw", "allow", port])
            logger.info(f"[firewall] Allowed custom port/service: {port}")
    shell.run(["sudo", "ufw", "logging", "on"])
    status = shell.run(["sudo", "ufw", "status"]) or ""
    if "OpenSSH" not in status:
        console.print("[red]Warning: SSH is not allowed in UFW rules. You may lock yourself out![/red]")
        logger.warning("[firewall] SSH is not allowed in UFW rules.")
    shell.run(["sudo", "ufw", "--force", "enable"])
    status = shell.run(["sudo", "ufw", "status", "verbose"]) or ""
    console.print(f"[blue]UFW is now enabled and configured.[/blue]\n\n{status}")
    logger.info(f"[firewall] UFW firewall configured.\n{status}") 