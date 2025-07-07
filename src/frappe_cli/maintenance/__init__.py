# This file marks the maintenance directory as a Python package.

import click
from .logrotate import logrotate

@click.group()
def maintenance():
    """Maintenance commands (logrotate, etc)."""
    pass

maintenance.add_command(logrotate) 