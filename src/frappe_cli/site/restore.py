import click
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.site.restore")
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
@click.option('--backup-file', prompt='Enter backup file path', help='Path to backup file to restore')
def restore(bench_name, site_name, backup_file):
    """Restore a site from backup (stub)."""
    click.secho(f"[STUB] Would restore site '{site_name}' from backup file '{backup_file}'. Not yet implemented.", fg="yellow") 