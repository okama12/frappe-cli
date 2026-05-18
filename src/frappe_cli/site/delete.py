import os
import shutil

import click
from rich.console import Console

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("site.delete")


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option(
    "--site-name",
    prompt="Enter site name (FQDN recommended)",
    default=lambda: os.uname()[1],
    show_default=True,
    help="Site name (FQDN)",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.pass_context
def delete(ctx, bench_name, site_name, dry_run, debug):
    """
    Delete a Frappe site (drops database and removes site folder).

    Example:
        frappe site delete --bench-name mybench --site-name example.com --debug
    """
    logger.info(f"[site] Deleting site: {site_name} from bench: {bench_name}")
    user_home = os.path.expanduser("~")
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    if not os.path.isdir(bench_path):
        console.print(f"[bold red]Bench directory '{bench_path}' not found.[/bold red]")
        logger.error(f"[site] Bench directory '{bench_path}' not found.")
        raise click.ClickException(f"Bench directory '{bench_path}' not found.")
    os.chdir(bench_path)
    site_path = f"sites/{site_name}"
    if not os.path.isdir(site_path):
        console.print(
            f"[yellow]Site '{site_name}' does not exist. Skipping deletion.[/yellow]"
        )
        logger.info(f"[site] Site '{site_name}' does not exist. Skipping.")
        return

    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="site.delete"
    )
    shell_runner.run(
        ["bench", "drop-site", site_name, "--no-backup"],
        f"Deleting site '{site_name}'",
        ignore_errors=ignore_errors,
    )
    # Always try to remove the site folder in case it's left over
    if os.path.isdir(site_path):
        if dry_run:
            console.print(f"[yellow][dry-run] Would remove folder: {site_path}")
            logger.info(f"[dry-run] Would remove folder: {site_path}")
        else:
            try:
                shutil.rmtree(site_path)
                console.print(f"[green]✓ Site folder '{site_path}' removed.[/green]")
                logger.info(f"[site] Site folder '{site_path}' removed.")
            except Exception as e:
                console.print(
                    f"[red]Failed to remove site folder '{site_path}': {e}[/red]"
                )
                logger.error(f"[site] Failed to remove site folder '{site_path}': {e}")
    logger.info(f"[site] Site deleted: {site_name}")
    console.print(f"[bold green]✓ Site deleted: {site_name}[/bold green]")
