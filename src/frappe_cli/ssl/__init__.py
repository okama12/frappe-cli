# This file marks the ssl directory as a Python package.

import click

from .list_certs import list_certs
from .setup import setup


@click.group()
def ssl():
    """SSL/HTTPS management commands."""
    pass


ssl.add_command(setup)
ssl.add_command(list_certs)
