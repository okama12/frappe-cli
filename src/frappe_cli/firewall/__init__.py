# This file marks the firewall directory as a Python package.

import click
from .setup import setup

@click.group()

def firewall():
    """Firewall management commands."""
    pass

firewall.add_command(setup)
