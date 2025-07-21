# This file marks the config directory as a Python package.

import click
from .set import set as set_cmd
from .get import get as get_cmd
from .validate import validate

@click.group()

def config():
    """Config file management commands (set/get/validate)."""
    pass

config.add_command(set_cmd, name='set')
config.add_command(get_cmd, name='get')
config.add_command(validate)
