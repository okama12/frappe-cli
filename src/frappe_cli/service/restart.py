import subprocess

import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("service.restart")


@click.command()
@click.option(
    "--bench-name", help="Bench directory name (auto-detected if not specified)"
)
@click.option("--site-name", help="Site name (auto-detected if not specified)")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be restarted without doing it"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
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
            subprocess.run(
                ["sudo", "systemctl", "restart", service],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]✓ {service} restarted successfully[/green]")
            logger.info(f"[service] Successfully restarted {service}")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to restart {service}: {e.stderr}[/red]")
            logger.error(f"[service] Failed to restart {service}: {e.stderr}")

    # If we have bench context, also restart bench services
    if bench_name:
        try:
            console.print("[blue]Restarting bench services...[/blue]")
            subprocess.run(
                ["bench", "restart"], check=True, capture_output=True, text=True
            )
            console.print("[green]✓ Bench services restarted successfully[/green]")
            logger.info("[service] Successfully restarted bench services")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Failed to restart bench services: {e.stderr}[/red]")
            logger.error(f"[service] Failed to restart bench services: {e.stderr}")

    console.print("[bold green]Service restart complete![/bold green]")
