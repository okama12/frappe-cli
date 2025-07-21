# This file marks the monitor directory as a Python package.

import click
from .logs import logs
from .health import health

@click.group()

def monitor():
    """Monitoring commands (logs, health, etc)."""
    pass

monitor.add_command(logs)
monitor.add_command(health)
