# This file marks the backup directory as a Python package.
import click

from .setup import setup


@click.group(invoke_without_command=True, no_args_is_help=False)
@click.option("--bench", default=None, help="Bench path; detected from cwd.")
@click.option("--site", "-s", default=None, help="Override the selected site.")
@click.option("--with-files", is_flag=True, help="Include public and private files.")
@click.option("--dry-run", is_flag=True, help="Preview without running backup.")
@click.pass_context
def backup(ctx, bench, site, with_files, dry_run):
    """Back up the selected site; use setup to configure scheduled backups."""
    if ctx.invoked_subcommand is not None:
        return
    from frappe_cli.dev.commands import _make_passthrough

    ctx.invoke(
        _make_passthrough("backup"),
        bench=bench,
        site=site,
        dry_run=dry_run,
        extra_args=("--with-files",) if with_files else (),
    )


backup.add_command(setup)
