import click
from frappe_cli.install import install
from frappe_cli.site import site
from frappe_cli.ssl import ssl
from frappe_cli.backup import backup
from frappe_cli.service import service
from frappe_cli.firewall import firewall
from frappe_cli.app import app
from frappe_cli.rollback import rollback
from frappe_cli.maintenance.logrotate import logrotate
from frappe_cli.config import config
from frappe_cli.monitor import monitor
from frappe_cli.optimize import optimize

@click.group()
@click.option('--config', type=click.Path(exists=True), help='Path to YAML config file')
@click.pass_context
def cli(ctx, config):
    """Frappe Installer CLI - Automate Frappe deployment and management."""
    ctx.ensure_object(dict)
    # Config loading is currently not used
    # from frappe_cli.config import load_config
    # ctx.obj['CONFIG'] = load_config(config)

cli.add_command(install)
cli.add_command(site)
cli.add_command(ssl)
cli.add_command(backup)
cli.add_command(service)
cli.add_command(firewall)
cli.add_command(app)
cli.add_command(rollback)
cli.add_command(logrotate)
cli.add_command(config)
cli.add_command(monitor)
cli.add_command(optimize)

if __name__ == "__main__":
    cli(obj={}) 