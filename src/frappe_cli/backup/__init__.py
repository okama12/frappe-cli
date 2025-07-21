# This file marks the backup directory as a Python package.
import click

from .setup import setup


@click.group()
def backup():
    """Backup management commands."""
    pass


backup.add_command(setup)
