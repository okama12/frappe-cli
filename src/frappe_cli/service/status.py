import click
import os
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"
SERVICES = ["mariadb", "redis-server", "nginx", "supervisor"]

def setup_logger():
    logger = logging.getLogger("frappe_installer.service.status")
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
@click.option('--site-name', prompt='Enter site name', default='', show_default=False, help='Frappe site name (optional)')
def status(bench_name, site_name):
    """Show system, service, and Frappe/Bench status."""
    logger.info("[service] Checking system status...")
    click.echo("=== System Information ===")
    click.echo(f"Hostname: {os.uname().nodename}")
    os_release = shell.run(["cat", "/etc/os-release"])
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME"):
            click.echo(f"OS: {line.split('=')[1].strip().strip('"')}")
    click.echo(f"Kernel: {os.uname().release}")
    mem = shell.run(["free", "-h"])
    for line in mem.splitlines():
        if line.startswith("Mem"):
            click.echo(f"Memory: {'/'.join(line.split()[2:4])}")
    disk = shell.run(["df", "-h", "/"])
    for line in disk.splitlines()[1:2]:
        parts = line.split()
        click.echo(f"Disk: {parts[2]}/{parts[1]} ({parts[4]} used)")
    click.echo()
    click.echo("=== Service Status ===")
    for service in SERVICES:
        status = os.system(f"systemctl is-active --quiet {service}")
        if status == 0:
            click.secho(f"{service}: Running", fg="green")
        else:
            click.secho(f"{service}: Stopped", fg="red")
    click.echo()
    click.echo("=== Frappe/Bench Status ===")
    if shell.run(["which", "bench"]):
        version = shell.run(["bench", "--version"])
        click.secho(f"Bench CLI: {version}", fg="green")
        if os.path.isdir(bench_name):
            click.secho(f"Bench directory: {bench_name} exists", fg="green")
            os.chdir(bench_name)
            if site_name and os.path.isdir(f"sites/{site_name}"):
                click.secho(f"Site: {site_name} exists", fg="green")
                try:
                    apps = shell.run(["bench", "--site", site_name, "list-apps"])
                    click.echo("Installed apps:")
                    for app in apps.splitlines():
                        click.echo(f"  - {app}")
                except Exception:
                    pass
            elif site_name:
                click.secho(f"Site: {site_name} not found", fg="red")
        else:
            click.secho(f"Bench directory: {bench_name} not found", fg="red")
    else:
        click.secho("Bench CLI: Not installed", fg="red")
    click.echo()
    click.echo("=== SSL Certificate ===")
    ssl_path = f"/etc/letsencrypt/live/{site_name}/fullchain.pem"
    if site_name and os.path.isfile(ssl_path):
        exp_date = shell.run(["openssl", "x509", "-enddate", "-noout", "-in", ssl_path])
        click.secho(f"SSL certificate valid until: {exp_date.split('=')[1]}", fg="green")
    else:
        click.secho(f"SSL certificate not found for {site_name}", fg="red")
    logger.info("[service] Status check completed.") 