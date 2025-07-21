# This file marks the install directory as a Python package.

import click

from .bench import bench
from .deps import deps
from .fail2ban import fail2ban
from .init import init
from .mariadb import mariadb
from .prod import prod
from .ssh_hardening import ssh_hardening
from .system import system
from .user import user


@click.group()
def install():
    """Install and setup commands for Frappe"""
    pass


install.add_command(bench)
install.add_command(deps)
install.add_command(fail2ban)
install.add_command(init)
install.add_command(mariadb)
install.add_command(prod)
install.add_command(ssh_hardening)
install.add_command(system)
install.add_command(user)
