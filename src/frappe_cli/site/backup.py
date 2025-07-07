import click
import os
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.backup")
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
@click.option('--bench-name', prompt='Enter bench name (folder)', default='frappe-bench', show_default=True, help='Bench directory name')
@click.option('--site-name', prompt='Enter site name', help='Frappe site name')
def backup(bench_name, site_name):
    """Run bench backup for a site."""
    if not os.path.isdir(bench_name):
        click.secho(f"Bench directory '{bench_name}' not found.", fg="red")
        logger.error(f"[site] Bench directory '{bench_name}' not found.")
        return
    os.chdir(bench_name)
    if not os.path.isdir(f"sites/{site_name}"):
        click.secho(f"Site '{site_name}' not found.", fg="red")
        logger.error(f"[site] Site '{site_name}' not found.")
        return
    shell.run(["bench", "--site", site_name, "backup"])
    click.secho(f"Backup completed for site: {site_name}", fg="green")
    logger.info(f"[site] Backup completed for site: {site_name}") 