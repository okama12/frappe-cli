"""``frappe rollback uninstall`` — remove a single bench safely.

This used to call ``sudo rm -rf <bench_name> /var/log/frappe-installer.log``
with no validation, which made a typo capable of nuking ``/etc`` or anything
else. The new implementation:

* Validates ``bench_name`` with a strict allowlist (``utils.validators``).
* Resolves the path under ``$HOME`` and refuses to act on anything outside it.
* Removes only the bench directory by default — never the system log.
* Requires the user to retype the bench name as a typed confirmation.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click
from rich.console import Console

from ..utils import shell
from ..utils.errors import ValidationError
from ..utils.logging import get_logger
from ..utils.validators import safe_bench_path, validate_site_name

LOG_FILE = Path("/var/log/frappe-installer.log")

console = Console()
logger = get_logger("rollback.uninstall")


@click.command()
@click.option(
    "--bench-name",
    prompt="Bench directory name",
    default="frappe-bench",
    show_default=True,
    help="Bench directory under $HOME to remove",
)
@click.option(
    "--site-name",
    prompt="Site name to back up before removal",
    help="Frappe site name (FQDN) to back up; ignored if it does not exist.",
)
@click.option(
    "--remove-log",
    is_flag=True,
    help=(
        "Also delete /var/log/frappe-installer.log. "
        "Off by default — your system log is preserved."
    ),
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the typed-name confirmation prompt (use in scripts).",
)
def uninstall(bench_name: str, site_name: str, remove_log: bool, yes: bool) -> None:
    """Remove a single Frappe bench safely.

    Example:

        fp rollback uninstall --bench-name mybench --site-name example.com
    """
    try:
        bench_path = safe_bench_path(bench_name)
        site_name = validate_site_name(site_name)
    except ValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    home = Path.home().resolve()
    if not bench_path.is_dir():
        raise click.ClickException(f"Bench directory not found: {bench_path}")
    if bench_path == home:
        raise click.ClickException(
            f"Refusing to remove the home directory itself ({bench_path})."
        )

    console.print(
        f"\n[bold red]About to remove[/bold red] [cyan]{bench_path}[/cyan] "
        f"(site [cyan]{site_name}[/cyan])."
    )
    if remove_log:
        console.print(f"[bold red]Will also remove[/bold red] [cyan]{LOG_FILE}[/cyan].")
    else:
        console.print(f"[dim]System log {LOG_FILE} will be preserved.[/dim]")

    if not yes:
        typed = click.prompt(
            f"Type the bench name '{bench_name}' to confirm",
            default="",
            show_default=False,
        )
        if typed != bench_name:
            console.print("[yellow]Confirmation mismatch — aborted.[/yellow]")
            raise click.Abort()

    logger.info(
        f"[rollback] Uninstall initiated for bench: {bench_name}, site: {site_name}"
    )

    # Try to back up the live site before removing files (best-effort).
    site_dir = bench_path / "sites" / site_name
    if site_dir.is_dir():
        try:
            shell.run(["bench", "--site", site_name, "backup"], cwd=str(bench_path))
            logger.info(f"[rollback] Backup created for site: {site_name}")
        except Exception as exc:  # noqa: BLE001 — best effort
            logger.warning(f"[rollback] Backup failed: {exc}")
            console.print(f"[yellow]Backup failed: {exc}[/yellow]")
    else:
        console.print(
            f"[dim]Site {site_name} not found under {bench_path}; "
            "skipping pre-remove backup.[/dim]"
        )

    # Final boundary check: never call rm -rf on anything outside $HOME.
    final_path = bench_path.resolve()
    try:
        final_path.relative_to(home)
    except ValueError as exc:  # pragma: no cover — defensive
        raise click.ClickException(
            f"Refusing to remove {final_path}: outside {home}"
        ) from exc

    # We have full write access to $HOME so we never need sudo here.
    console.print(f"[red]Removing[/red] {final_path} …")
    shutil.rmtree(final_path, ignore_errors=False)

    if remove_log:
        if os.geteuid() == 0:
            try:
                LOG_FILE.unlink(missing_ok=True)
            except OSError as exc:
                console.print(f"[yellow]Could not remove {LOG_FILE}: {exc}[/yellow]")
        else:
            shell.run(["sudo", "rm", "-f", str(LOG_FILE)])

    logger.info(
        f"[rollback] Uninstall complete for bench: {bench_name}, site: {site_name}"
    )
    console.print("[green]✓ Uninstall complete.[/green]")
