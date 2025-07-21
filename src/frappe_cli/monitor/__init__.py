# This file marks the monitor directory as a Python package.

import click

from .health import health
from .logs import logs


@click.group()
def monitor():
    """Monitoring commands (logs, health, etc)."""
    pass


monitor.add_command(logs)
monitor.add_command(health)
