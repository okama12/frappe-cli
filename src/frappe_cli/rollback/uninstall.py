import os

import click
from rich.console import Console

from ..utils import shell
from ..utils.logging import get_logger

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()
logger = get_logger("rollback.uninstall")


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option("--site-name", prompt="Enter site name", help="Frappe site name")
def uninstall(bench_name, site_name):
    """
    Remove the bench, site, and optionally logs.

    Example:
        frappe rollback uninstall --bench-name mybench --site-name example.com
    """
    logger.info(
        f"[rollback] Uninstall initiated for bench: {bench_name}, site: {site_name}"
    )
    if not click.confirm(
        f"This will remove the bench '{bench_name}', site '{site_name}', and optionally logs. Continue?",
        abort=True,
    ):
        logger.info("[rollback] Uninstall cancelled by user.")
        return

    # Backup database if possible
    if os.path.isdir(bench_name):
        os.chdir(bench_name)
        if os.path.isdir(f"sites/{site_name}"):
            try:
                shell.run(["bench", "--site", site_name, "backup"])
                logger.info(f"[rollback] Backup created for site: {site_name}")
            except Exception as e:
                logger.warning(f"[rollback] Backup failed: {e}")
        os.chdir("..")
        backup_file = f"{bench_name}_backup_$(date +%F).tar.gz"
        shell.run(["tar", "czf", backup_file, bench_name, LOG_FILE], check=False)
        logger.info(f"[rollback] Backup archive created: {backup_file}")
    # Remove bench and logs
    shell.run(["sudo", "rm", "-rf", bench_name, LOG_FILE])
    logger.info(
        f"[rollback] Uninstall complete for bench: {bench_name}, site: {site_name}"
    )
    console.print("[green]Uninstall complete.[/green]")
