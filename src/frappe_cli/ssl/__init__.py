# This file marks the ssl directory as a Python package.

import click

from .list_certs import list_certs
from .secure import secure
from .setup import setup


class SSLGroup(click.Group):
    """Recognize existing subcommands before routing DOMAIN to HTTPS setup."""

    def parse_args(self, ctx, args):
        if not args or args[0] not in {"setup", "list", "secure", "--help"}:
            args = ["secure", *args]
        return super().parse_args(ctx, args)

    def format_usage(self, ctx, formatter):
        formatter.write_usage(ctx.command_path, "[DOMAIN] [OPTIONS] | list | setup")

    def format_options(self, ctx, formatter):
        secure.format_options(ctx, formatter)
        self.format_commands(ctx, formatter)


@click.group(cls=SSLGroup, no_args_is_help=False)
def ssl():
    """Configure HTTPS for a domain, with or without Frappe.

    Examples: fp ssl example.com · fp ssl example.com --email you@example.com
    """
    pass


ssl.add_command(setup)
ssl.add_command(list_certs)
ssl.add_command(secure)
