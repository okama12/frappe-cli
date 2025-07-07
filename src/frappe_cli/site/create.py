import click
import os
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.create")
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
@click.option('--site-name', prompt='Enter site name (FQDN recommended)', default=lambda: os.uname()[1], show_default=True, help='Site name (FQDN)')
@click.option('--mariadb-root-password', prompt='Enter MariaDB root password', hide_input=True, help='MariaDB root password')
@click.option('--admin-password', prompt='Enter Frappe Admin password', hide_input=True, help='Frappe Admin password')
def create(bench_name, site_name, mariadb_root_password, admin_password):
    """Create a new Frappe site."""
    logger.info(f"[site] Creating site: {site_name} in bench: {bench_name}")
    if not os.path.isdir(bench_name):
        click.secho(f"Bench directory '{bench_name}' not found.", fg="red")
        logger.error(f"[site] Bench directory '{bench_name}' not found.")
        return
    os.chdir(bench_name)
    if os.path.isdir(f"sites/{site_name}"):
        click.secho(f"Site '{site_name}' already exists. Skipping creation.", fg="yellow")
        logger.info(f"[site] Site '{site_name}' already exists. Skipping.")
        return
    shell.run([
        "bench", "new-site", site_name,
        "--mariadb-root-password", mariadb_root_password,
        "--admin-password", admin_password
    ])
    logger.info(f"[site] Site created: {site_name}")
    click.secho(f"Site created: {site_name}", fg="green") 