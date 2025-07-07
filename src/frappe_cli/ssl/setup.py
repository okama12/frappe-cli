import click
import os
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.ssl.setup")
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
@click.option('--site-name', prompt='Enter site name (domain)', help='Domain for SSL certificate')
@click.option('--email', prompt='Enter your email for Let\'s Encrypt notifications', help='Email for Let\'s Encrypt')
def setup(site_name, email):
    """Set up SSL/HTTPS with Let's Encrypt (Certbot)."""
    logger.info(f"[ssl] Setting up SSL for domain: {site_name}")
    if not shell.run(["which", "certbot"]):
        click.echo("Certbot not found. Installing certbot...")
        shell.run(["sudo", "apt", "install", "-y", "certbot", "python3-certbot-nginx"])
    # Check DNS
    if os.system(f"host {site_name} > /dev/null 2>&1") != 0:
        click.secho(f"DNS for {site_name} is not set up. Please configure DNS and try again.", fg="red")
        logger.error(f"[ssl] DNS for {site_name} not set up.")
        return
    # Check port 80
    if os.system(f"timeout 2 bash -c '</dev/tcp/{site_name}/80' > /dev/null 2>&1") != 0:
        click.secho(f"Port 80 on {site_name} is not reachable. Ensure your domain points to this server and port 80 is open.", fg="red")
        logger.error(f"[ssl] Port 80 on {site_name} not reachable.")
        return
    shell.run(["sudo", "certbot", "--nginx", "-d", site_name, "--non-interactive", "--agree-tos", "-m", email])
    shell.run(["sudo", "systemctl", "enable", "certbot.timer"])
    shell.run(["sudo", "systemctl", "start", "certbot.timer"])
    logger.info(f"[ssl] SSL/HTTPS set up for {site_name}. Auto-renewal enabled.")
    click.secho(f"SSL/HTTPS set up for {site_name}. Auto-renewal enabled.", fg="green") 