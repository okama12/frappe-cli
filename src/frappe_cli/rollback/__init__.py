# This file marks the rollback directory as a Python package.

import click

from .uninstall import uninstall


@click.group()
def rollback():
    """Rollback/uninstall commands."""
    pass


rollback.add_command(uninstall)
