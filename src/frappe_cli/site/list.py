import click
import os
import glob
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.list")
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
def list(bench_name):
    """List all Frappe sites in the bench."""
    sites_path = os.path.join(bench_name, 'sites')
    if not os.path.isdir(sites_path):
        click.secho(f"Bench directory '{bench_name}' or sites folder not found.", fg="red")
        logger.error(f"[site] Bench directory '{bench_name}' or sites folder not found.")
        return
    sites = [os.path.basename(d) for d in glob.glob(os.path.join(sites_path, '*')) if os.path.isdir(d) and d != 'assets']
    if not sites:
        click.secho("No sites found.", fg="yellow")
        return
    click.secho("Sites:", fg="green")
    for s in sites:
        click.echo(f"- {s}") 