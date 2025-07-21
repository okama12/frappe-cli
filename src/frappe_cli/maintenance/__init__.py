# This file marks the maintenance directory as a Python package.

__all__ = ["maintenance"]

import click
@click.group()

def maintenance():
    """Maintenance commands (logrotate, etc)."""
    pass

def _register_subcommands():
    from .logrotate_cmd import logrotate_maintenance
    maintenance.add_command(logrotate_maintenance, "logrotate")

_register_subcommands()
