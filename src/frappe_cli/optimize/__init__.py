# This file marks the optimize directory as a Python package.

import click
from .performance import performance

@click.group()
def optimize():
    """Performance tuning commands (stub)."""
    pass

optimize.add_command(performance) 