import glob
import os

import click
from rich.console import Console

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("site.list")


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
def list(bench_name, dry_run, debug, ignore_errors):
    """List all Frappe sites in the bench."""
    logger.info(f"[site] Listing sites in bench: {bench_name}")
    user_home = os.path.expanduser("~")
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    sites_path = os.path.join(bench_path, "sites")
    if not os.path.isdir(sites_path):
        console.print(
            f"[bold red]Bench directory '{bench_path}' or sites folder not found.[/bold red]"
        )
        logger.error(
            f"[site] Bench directory '{bench_path}' or sites folder not found."
        )
        raise click.ClickException(
            f"Bench directory '{bench_path}' or sites folder not found."
        )
    sites = [
        os.path.basename(d)
        for d in glob.glob(os.path.join(sites_path, "*"))
        if os.path.isdir(d) and os.path.basename(d) != "assets"
    ]
    if not sites:
        console.print("[yellow]No sites found.[/yellow]")
        return

    console.print("[green]Sites and installed apps:[/green]")
    _shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="site.list"
    )
    for s in sites:
        _site_path = os.path.join(sites_path, s)
        # Run bench command from the bench directory
        try:
            prev_cwd = os.getcwd()
            os.chdir(bench_path)
            result = os.popen(f"bench --site {s} list-apps").read().strip()
            os.chdir(prev_cwd)
            apps = result.splitlines() if result else []
        except Exception as e:
            logger.error(f"[site] Failed to run bench list-apps for site {s}: {e}")
            apps = []
        apps_str = ", ".join(apps) if apps else "[none]"
        console.print(f"- [bold]{s}[/bold]: [cyan]{apps_str}[/cyan]")
    logger.info(
        f"[site] Listed {len(sites)} sites and their apps in bench {bench_name}"
    )
