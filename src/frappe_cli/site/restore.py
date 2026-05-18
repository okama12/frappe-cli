import os

import click
from rich.console import Console

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("site.restore")


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option("--site-name", prompt="Enter site name", help="Frappe site name")
@click.option(
    "--backup-file",
    prompt="Enter backup file path",
    help="Path to backup file to restore",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
def restore(bench_name, site_name, backup_file, dry_run, debug, ignore_errors):
    """Restore a site from backup."""
    logger.info(
        f"[site] Restoring site: {site_name} from backup: {backup_file} in bench: {bench_name}"
    )
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
    site_path = os.path.join("sites", site_name)
    if not os.path.isdir(site_path):
        console.print(
            f"[bold red]Site '{site_name}' not found in bench '{bench_path}'.[/bold red]"
        )
        logger.error(f"[site] Site '{site_name}' not found in bench '{bench_path}'.")
        raise click.ClickException(
            f"Site '{site_name}' not found in bench '{bench_path}'."
        )
    if not os.path.isfile(backup_file):
        console.print(f"[bold red]Backup file '{backup_file}' not found.[/bold red]")
        logger.error(f"[site] Backup file '{backup_file}' not found.")
        raise click.ClickException(f"Backup file '{backup_file}' not found.")
    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="site.restore"
    )
    shell_runner.run(
        ["bench", "--site", site_name, "--force", "restore", backup_file],
        f"Restoring site '{site_name}' from backup '{backup_file}'",
        ignore_errors=ignore_errors,
    )
    logger.info(f"[site] Restore completed for site: {site_name}")
    console.print(f"[bold green]✓ Restore completed for site: {site_name}[/bold green]")
