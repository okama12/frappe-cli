# This file marks the app directory as a Python package.

import click
from .clone import clone

@click.group()

def app():
    """App management commands."""
    pass

app.add_command(clone)
