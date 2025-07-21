import click
import os
from pathlib import Path
from rich.prompt import Prompt
import getpass

from ..utils.context import create_context, CliContext
from ..utils.shell import RichShellRunner
from ..utils.logging import get_logger
from ..utils.validators import validate_directory_exists, validate_not_empty
from ..utils.errors import ResourceNotFoundError, ValidationError

@click.command()
@click.option('--bench-name', prompt='Enter bench name (folder)',
              default='frappe-bench', show_default=True,
              help='Bench directory name')
@click.option('--site-name', prompt='Enter site name (FQDN recommended)',
              default=lambda: os.uname()[1], show_default=True,
              help='Site name (FQDN)')
@click.option('--dry-run', is_flag=True,
              help='Simulate commands without executing them')
@click.option('--debug', is_flag=True,
              help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True,
              help='Continue despite errors')
@click.pass_context

def create(ctx: click.Context,
          bench_name: str,
          site_name: str,
          dry_run: bool,
          debug: bool,
          ignore_errors: bool) -> None:
    """
    Create a new Frappe site.

    Example:
        frappe site create --bench-name mybench --site-name example.com --debug
    """
    # Create a CLI context for this command
    context = create_context(
        module_name="site.create",
        dry_run=dry_run,
        debug=debug,
        ignore_errors=ignore_errors
    )

    # Log the operation
    context.logger.info(f"Creating site: {site_name} in bench: {bench_name}")

    # Validate inputs
    validate_not_empty(bench_name, "Bench name cannot be empty")
    validate_not_empty(site_name, "Site name cannot be empty")

    # Resolve bench path to user's home if not absolute
    user_home = Path.home()
    bench_path = Path(bench_name)
    if not bench_path.is_absolute():
        bench_path = user_home / bench_name

    # Validate bench directory exists
    try:
        validate_directory_exists(
            bench_path,
            f"Bench directory '{bench_path}' not found"
        )

    except (ResourceNotFoundError, ValidationError) as e:
        context.console.print(f"[bold red]{e.message}[/bold red]")
        context.logger.error(f"Bench directory '{bench_path}' not found")
        raise click.ClickException(e.message)

    # Change to bench directory
    os.chdir(bench_path)

    # Check if site already exists
    site_path = bench_path / "sites" / site_name
    site_config_path = site_path / "site_config.json"

    if site_path.is_dir():
        if not site_config_path.is_file():
            error_msg = (
                f"Site folder '{site_name}' exists but is incomplete (missing site_config.json).\n"
                "You may want to delete it and try again."
            )

            context.console.print(f"[red]{error_msg}[/red]")
            context.logger.error(f"Site folder '{site_name}' exists but is incomplete")
            raise click.ClickException(error_msg)

        context.console.print(f"[yellow]Site '{site_name}' already exists. Skipping creation.[/yellow]")
        context.logger.info(f"Site '{site_name}' already exists. Skipping.")
        return

    # Create the site
    context.shell.run(
        cmd=["bench", "new-site", site_name],
        description=f"Creating new site '{site_name}'",
        ignore_errors=ignore_errors
    )

    context.logger.info(f"Site created: {site_name}")
    context.console.print(f"[bold green]✓ Site created: {site_name}[/bold green]")
