import os

import click
from rich.console import Console

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("site.add")


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option(
    "--site-name", prompt="Enter site name", help="Site name to install the app on"
)
@click.option("--app-name", prompt="Enter app name", help="App name to install")
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
def add(bench_name, site_name, app_name, dry_run, debug, ignore_errors):
    """Install a Frappe app on a site."""
    logger.info(
        f"[site] Installing app: {app_name} on site: {site_name} in bench: {bench_name}"
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
    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="site.add"
    )
    shell_runner.run(
        ["bench", "--site", site_name, "install-app", app_name],
        f"Installing app '{app_name}' on site '{site_name}'",
        ignore_errors=ignore_errors,
    )
    logger.info(f"[site] App {app_name} installed on site {site_name}")
    console.print(
        f"[bold green]✓ App {app_name} installed on site {site_name}[/bold green]"
    )
    # Optionally, show installed apps
    shell_runner.run(
        ["bench", "--site", site_name, "list-apps"],
        f"Listing installed apps on site '{site_name}'",
        ignore_errors=ignore_errors,
    )
