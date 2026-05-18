import os

import click
from rich.console import Console
from rich.prompt import Prompt

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("install.init")


def validate_sudo():
    console.print("[yellow]Validating sudo access[/yellow]")
    result = os.system("sudo -v")
    if result != 0:
        console.print(
            "[bold red]✗ Sudo validation failed. Please ensure you have sudo privileges.[/bold red]"
        )
        raise click.ClickException("Sudo validation failed.")
    console.print("[bold green]✓ Sudo privileges validated[/bold green]")


@click.command()
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
@click.pass_context
def init(ctx, dry_run, debug, ignore_errors):
    """Create new Frappe Bench instance."""
    validate_sudo()
    config = ctx.obj.get("CONFIG", {})
    bench_name = config.get("frappe", {}).get("bench_name") or "frappe-bench"
    bench_name = Prompt.ask(
        f"Enter bench name (folder) [default: {bench_name}]", default=bench_name
    )
    user_home = os.path.expanduser("~")
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    frappe_branch = config.get("frappe", {}).get("branch") or "version-15"
    frappe_branch = Prompt.ask(
        f"Enter Frappe branch to use [default: {frappe_branch}]", default=frappe_branch
    )
    logger.info(
        f"[init] Creating bench instance: {bench_path} (branch: {frappe_branch})"
    )
    if os.path.isdir(bench_path):
        console.print(
            f"[yellow]Bench directory '{bench_path}' already exists. Skipping initialization.[/yellow]"
        )
        logger.info(f"[init] Bench directory '{bench_path}' already exists. Skipping.")
        return

    console.print(
        f"[cyan]Initializing bench: {bench_path} (branch: {frappe_branch})[/cyan]"
    )
    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="install.init"
    )
    shell_runner.run(
        ["bench", "init", "--frappe-branch", frappe_branch, bench_path],
        "Initializing Frappe Bench",
        ignore_errors=ignore_errors,
    )
    logger.info(f"[init] Bench initialized successfully: {bench_path}")
    console.print(
        f"[bold green]✓ Bench initialized successfully: {bench_path}[/bold green]"
    )
