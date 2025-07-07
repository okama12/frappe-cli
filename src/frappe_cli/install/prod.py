import click
from ..utils import shell
import logging
import os

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.prod")
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
def prod(ctx):
    """Setup production environment for Frappe."""
    config = ctx.obj.get('CONFIG', {})
    bench_name = config.get('frappe', {}).get('bench_name', 'frappe-bench')
    bench_name = click.prompt('Enter bench name (folder)', default=bench_name, show_default=True)
    logger.info(f"[prod] Setting up production environment for bench: {bench_name}")
    if not os.path.isdir(bench_name):
        click.secho(f"Bench directory '{bench_name}' not found.", fg="red")
        logger.error(f"[prod] Bench directory '{bench_name}' not found.")
        return
    os.chdir(bench_name)
    bench_cmd = shell.run(["which", "bench"])
    if not bench_cmd:
        click.secho("Bench command not found in PATH. Please ensure bench is installed.", fg="red")
        logger.error("[prod] Bench command not found in PATH.")
        return
    shell.run(["sudo", bench_cmd, "setup", "production", os.getenv("USER")])
    shell.run(["sudo", "systemctl", "restart", "supervisor", "nginx"])
    shell.run(["sudo", "systemctl", "enable", "supervisor", "nginx"])
    logger.info(f"[prod] Production environment configured for bench: {bench_name}")
    click.secho(f"Production environment configured for bench: {bench_name}", fg="green") 