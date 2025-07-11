# This file marks the site directory as a Python package. 

import click
from .backup import backup
from .create import create
from .list import list as list_sites
from .restore import restore
from .add import add
from .delete import delete

@click.group()
def site():
    """Site management commands."""
    pass

site.add_command(backup)
site.add_command(create)
site.add_command(add)
site.add_command(list_sites, name='list')
site.add_command(restore)
site.add_command(delete)