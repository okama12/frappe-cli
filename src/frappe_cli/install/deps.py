import click
from ..utils import shell
import logging
import os

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.deps")
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
def deps(ctx):
    """Install system dependencies for Frappe/ERPNext."""
    config = ctx.obj.get('CONFIG', {})
    default_deps = 'python,mariadb,redis,pdf,node,tools,bench-deps,mail'
    deps_val = config.get('system', {}).get('deps', default_deps)
    deps = click.prompt('Select dependencies (comma-separated)', default=deps_val, show_default=True)
    logger.info(f"[deps] Installing dependencies: {deps}")
    selected = [d.strip() for d in deps.split(',') if d.strip()]
    if 'python' in selected:
        click.echo("Installing Python dependencies...")
        shell.run(["sudo", "apt", "install", "-y", "python3-dev", "python3-venv", "python3-pip", "python3-setuptools", "python3-wheel", "pipx"])
        shell.run(["pipx", "ensurepath"])
    if 'mariadb' in selected:
        click.echo("Installing MariaDB...")
        shell.run(["sudo", "apt", "install", "-y", "mariadb-server", "mariadb-client"])
        shell.run(["sudo", "systemctl", "enable", "mariadb"])
        shell.run(["sudo", "systemctl", "start", "mariadb"])
    if 'redis' in selected:
        click.echo("Installing Redis...")
        shell.run(["sudo", "apt", "install", "-y", "redis-server"])
        shell.run(["sudo", "systemctl", "enable", "redis-server"])
        shell.run(["sudo", "systemctl", "start", "redis-server"])
    if 'pdf' in selected:
        click.echo("Installing PDF dependencies...")
        shell.run(["sudo", "apt", "install", "-y", "xvfb", "libfontconfig1", "wkhtmltopdf", "fonts-dejavu-core"])
    if 'node' in selected:
        click.echo("Installing Node.js via NVM...")
        nvm_dir = os.path.expanduser("~/.nvm")
        if not os.path.isdir(nvm_dir):
            shell.run(["curl", "-o-", "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh"], capture_output=False)
            shell.run(["bash", os.path.join(nvm_dir, "install.sh")], capture_output=False)
        shell.run(["bash", "-c", f"source {nvm_dir}/nvm.sh && nvm install 18 && nvm use 18 && nvm alias default 18"])
        shell.run(["bash", "-c", f"source {nvm_dir}/nvm.sh && node -v && npm -v"])
    if 'tools' in selected:
        click.echo("Installing development tools...")
        shell.run(["sudo", "apt", "install", "-y", "build-essential", "libssl-dev", "libffi-dev", "python3-dev", "libjpeg-dev", "zlib1g-dev"])
    if 'bench-deps' in selected:
        click.echo("Installing Bench dependencies...")
        shell.run(["sudo", "apt", "install", "-y", "supervisor", "nginx", "ufw"])
        shell.run([
            "bash", "-c",
            "curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | sudo tee /etc/apt/trusted.gpg.d/yarn.gpg > /dev/null"
        ])
        shell.run(["sudo", "tee", "/etc/apt/sources.list.d/yarn.list"], capture_output=False)
        shell.run(["sudo", "apt", "update"])
        shell.run(["sudo", "apt", "install", "-y", "yarn", "pipx"])
        shell.run(["pipx", "ensurepath"])
        shell.run(["sudo", "systemctl", "enable", "supervisor", "nginx"])
        shell.run(["sudo", "systemctl", "start", "supervisor", "nginx"])
    if 'mail' in selected:
        click.echo("Installing mail utilities...")
        shell.run(["sudo", "apt", "install", "-y", "mailutils"])
    logger.info("[deps] Dependencies installed successfully.")
    click.secho("Dependencies installed successfully!", fg="green") 