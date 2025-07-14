import click
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import logging
import getpass

LOG_FILE = "/var/log/frappe-installer.log" if getpass.getuser() == "root" else "frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.service.restart")
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(LOG_FILE)
    except PermissionError:
        handler = logging.FileHandler("frappe-installer.log")
    formatter = logging.Formatter('[%(asctime)s] %(message)s')
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

logger = setup_logger()

@click.command()
@click.option('--bench-name', help='Bench directory name (auto-detected if not specified)')
@click.option('--site-name', help='Site name (auto-detected if not specified)')
@click.option('--dry-run', is_flag=True, help='Show what would be restarted without doing it')
@click.option('--debug', is_flag=True, help='Enable debug output')
def restart(bench_name, site_name, dry_run, debug):
    """
    Restart Frappe services.

    Example:
        frappe service restart --bench-name mybench --site-name example.com --dry-run
    """
    logger.info("[service] Restarting Frappe services")
    
    if dry_run:
        console.print("[yellow]DRY RUN: Would restart the following services:[/yellow]")
        services = ["mariadb", "redis-server", "nginx", "supervisor"]
        for service in services:
            console.print(f"  - {service}")
        return
    
    # Services to restart
    services = ["mariadb", "redis-server", "nginx", "supervisor"]
    
    for service in services:
        try:
            console.print(f"[blue]Restarting {service}...[/blue]")
            result = subprocess.run(["sudo", "systemctl", "restart", service], 
                                  check=True, capture_output=True, text=True)
            console.print(f"[green]✓ {service} restarted successfully[/green]")
            logger.info(f"[service] Successfully restarted {service}")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to restart {service}: {e.stderr}[/red]")
            logger.error(f"[service] Failed to restart {service}: {e.stderr}")
    
    # If we have bench context, also restart bench services
    if bench_name:
        try:
            console.print("[blue]Restarting bench services...[/blue]")
            result = subprocess.run(["bench", "restart"], 
                                  check=True, capture_output=True, text=True)
            console.print("[green]✓ Bench services restarted successfully[/green]")
            logger.info("[service] Successfully restarted bench services")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to restart bench services: {e.stderr}[/red]")
            logger.error(f"[service] Failed to restart bench services: {e.stderr}")
    
    console.print("[bold green]Service restart complete![/bold green]") 