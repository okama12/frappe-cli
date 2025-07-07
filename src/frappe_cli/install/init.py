import click
from ..utils import shell
import logging
import os

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.init")
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
@click.pass_context
def init(ctx):
    """Create new Frappe Bench instance."""
    config = ctx.obj.get('CONFIG', {})
    bench_name = config.get('frappe', {}).get('bench_name', 'frappe-bench')
    bench_name = click.prompt('Enter bench name (folder)', default=bench_name, show_default=True)
    frappe_branch = config.get('frappe', {}).get('branch', 'version-15')
    frappe_branch = click.prompt('Enter Frappe branch to use', default=frappe_branch, show_default=True)
    logger.info(f"[init] Creating bench instance: {bench_name} (branch: {frappe_branch})")
    if os.path.isdir(bench_name):
        click.secho(f"Bench directory '{bench_name}' already exists. Skipping initialization.", fg="yellow")
        logger.info(f"[init] Bench directory '{bench_name}' already exists. Skipping.")
        return
    shell.run(["bench", "init", "--frappe-branch", frappe_branch, bench_name])
    logger.info(f"[init] Bench initialized successfully: {bench_name}")
    click.secho(f"Bench initialized successfully: {bench_name}", fg="green") 