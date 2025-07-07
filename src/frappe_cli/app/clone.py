import click
import os
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.app.clone")
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
@click.option('--repo-url', prompt='Enter the GitHub repository URL for the app', help='GitHub repository URL')
@click.option('--branch', prompt='Enter the branch to clone', default='main', show_default=True, help='Branch to clone')
def clone(bench_name, repo_url, branch):
    """Clone and validate a Frappe-compatible app from GitHub."""
    logger.info(f"[app] Cloning app from {repo_url} (branch: {branch}) into bench: {bench_name}")
    if not os.path.isdir(bench_name):
        click.secho(f"Bench directory '{bench_name}' not found.", fg="red")
        logger.error(f"[app] Bench directory '{bench_name}' not found.")
        return
    os.chdir(bench_name)
    shell.run(["bench", "get-app", "--branch", branch, repo_url])
    app_name = os.path.basename(repo_url).replace('.git', '')
    app_path = f"apps/{app_name}"
    if not (os.path.isfile(f"{app_path}/hooks.py") and os.path.isfile(f"{app_path}/__init__.py")):
        click.secho(f"App {app_name} does not appear to be Frappe-compatible (missing hooks.py or __init__.py)", fg="red")
        logger.error(f"[app] App {app_name} missing hooks.py or __init__.py")
        return
    reqs_path = f"{app_path}/requirements.txt"
    setup_path = f"{app_path}/setup.py"
    reqs_has_frappe = os.path.isfile(reqs_path) and 'frappe' in open(reqs_path).read()
    setup_has_frappe = os.path.isfile(setup_path) and 'frappe' in open(setup_path).read()
    if not (reqs_has_frappe or setup_has_frappe):
        click.secho(f"App {app_name} does not list 'frappe' as a dependency.", fg="red")
        logger.error(f"[app] App {app_name} does not list 'frappe' as a dependency.")
        return
    logger.info(f"[app] App {app_name} cloned and validated as Frappe-compatible.")
    click.secho(f"App {app_name} cloned and validated as Frappe-compatible.", fg="green") 