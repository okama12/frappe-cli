"""Task-oriented setup entry point, sharing operations with direct commands."""

import shutil

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from frappe_cli.dev.context import discover_benches, list_sites
from frappe_cli.install.wizard import wizard
from frappe_cli.ui import terminal
from frappe_cli.ui.panels import print_header

TASKS = [
    ("production", "Deploy a production Frappe server"),
    ("development", "Prepare a development bench and site"),
    ("site", "Add a site to an existing bench"),
    ("app", "Install an app on an existing site"),
    ("ssl", "Configure HTTPS for a domain"),
    ("inspect", "Inspect existing benches and tools"),
    ("custom", "Choose installation components"),
]


@click.command("inspect")
def inspect_environment():
    """Show discovered benches and installed tools without making changes."""
    console = Console()
    print_header(console)
    table = Table("Tool", "Location", box=None, expand=False)
    for tool in ("bench", "uv", "node", "redis-server", "mysql", "nginx", "certbot"):
        table.add_row(tool, Text(shutil.which(tool) or "Not found", style="dim"))
    console.print(table)
    benches = discover_benches()
    for bench in benches:
        console.print(Text(f"\n{bench}", style="bold"))
        for site in list_sites(bench):
            console.print(Text(f"  {site}"))
    if not benches:
        console.print(
            "No benches discovered in the current directory or directly under home.",
            style="dim",
        )


@click.command("setup")
@click.option(
    "--task",
    type=click.Choice([value for value, _ in TASKS]),
    default=None,
    help="Skip task selection; useful for redirected input.",
)
@click.option("--resume", is_flag=True, help="Resume the saved installation plan.")
@click.option("--dry-run", is_flag=True, help="Review without changing the server.")
@click.option("--debug", is_flag=True, help="Show detailed output.")
@click.option(
    "--skip-ssl", is_flag=True, help="Leave HTTPS for later during production setup."
)
@click.option(
    "--components",
    default=None,
    help="Comma-separated component IDs for a custom plan.",
)
@click.pass_context
def setup(ctx, task, resume, dry_run, debug, skip_ssl, components):
    """Guided setup: choose a task, review the plan, and follow progress."""
    if resume:
        if task is not None or components is not None:
            raise click.UsageError(
                "--resume uses the saved plan; omit --task and --components."
            )
        ctx.invoke(wizard, resume=True, dry_run=dry_run, debug=debug, skip_ssl=skip_ssl)
        return
    if task is None:
        if components is not None:
            task = "custom"
        else:
            if not terminal.interactive():
                raise click.UsageError(
                    "Choose --task production, development, site, app, ssl, inspect, or custom when input is redirected."
                )
            print_header(Console())
            task = terminal.choose("What would you like to do?", TASKS)
    if components is not None and task != "custom":
        raise click.UsageError("--components requires --task custom.")
    if task in {"production", "development", "custom"}:
        if task == "custom" and components is None and not terminal.interactive():
            raise click.UsageError(
                "Pass --components when selecting a custom plan without a terminal."
            )
        ctx.invoke(
            wizard,
            resume=False,
            dry_run=dry_run,
            debug=debug,
            skip_ssl=skip_ssl,
            components=(components or "") if task == "custom" else None,
            profile="development" if task == "development" else "production",
        )
        return
    if task == "inspect":
        ctx.invoke(inspect_environment)
        return
    name = {"site": "new", "app": "add", "ssl": "ssl"}[task]
    command = ctx.find_root().command.get_command(ctx.find_root(), name)
    if name == "ssl":
        from frappe_cli.ssl.secure import secure

        ctx.invoke(secure, dry_run=dry_run)
    else:
        ctx.invoke(command, dry_run=dry_run, debug=debug)
