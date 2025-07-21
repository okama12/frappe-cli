# This file marks the service directory as a Python package.

import click
from .restart import restart
from .status import status

@click.group()

def service():
    """Service management commands."""
    pass

service.add_command(restart)
service.add_command(status)
