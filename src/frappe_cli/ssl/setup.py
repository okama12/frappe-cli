import click
from rich.console import Console

from ..utils import shell
from ..utils.logging import get_logger

console = Console()
logger = get_logger("ssl.setup")


@click.command()
@click.option(
    "--site-name", prompt="Enter site name (domain)", help="Domain for SSL certificate"
)
@click.option(
    "--email",
    prompt="Enter your email for Let's Encrypt notifications",
    help="Email for Let's Encrypt",
)
def setup(site_name, email):
    """
    Set up SSL/HTTPS with Let's Encrypt (Certbot).

    Example:
        frappe ssl setup --site-name example.com --email user@example.com
    """
    logger.info(f"[ssl] Setting up SSL for domain: {site_name}")
    if not shell.run(["which", "certbot"]):
        console.print("[blue]Certbot not found. Installing certbot...[/blue]")
        shell.run(["sudo", "apt", "install", "-y", "certbot", "python3-certbot-nginx"])
    # Check DNS
    try:
        shell.run(["host", site_name], check=False)
    except Exception as e:
        console.print(
            f"[red]DNS for {site_name} is not set up. Please configure DNS and try again.[/red]"
        )
        logger.error(f"[ssl] DNS for {site_name} not set up: {e}")
        return

    # Check port 80
    try:
        shell.run(
            ["timeout", "2", "bash", "-c", f"</dev/tcp/{site_name}/80"], check=False
        )
    except Exception as e:
        console.print(
            f"[red]Port 80 on {site_name} is not reachable. Ensure your domain points to this server and port 80 is open.[/red]"
        )
        logger.error(f"[ssl] Port 80 on {site_name} not reachable: {e}")
        return

    shell.run(
        [
            "sudo",
            "certbot",
            "--nginx",
            "-d",
            site_name,
            "--non-interactive",
            "--agree-tos",
            "-m",
            email,
        ]
    )
    shell.run(["sudo", "systemctl", "enable", "certbot.timer"])
    shell.run(["sudo", "systemctl", "start", "certbot.timer"])
    logger.info(f"[ssl] SSL/HTTPS set up for {site_name}. Auto-renewal enabled.")
    console.print(
        f"[green]SSL/HTTPS set up for {site_name}. Auto-renewal enabled.[/green]"
    )
