"""``fp site delete`` — drop a Frappe site (with optional pre-delete backup).

Security/UX fixes vs. the previous implementation:

* The old code referenced an undefined ``ignore_errors`` variable inside
  :class:`RichShellRunner.run` — calling the command would always crash with a
  ``NameError``. The flag is now bound to ``--ignore-errors``.
* It hard-coded ``--no-backup`` for ``bench drop-site``. Site deletion is
  irreversible; we now default to **with backup** and require an explicit
  ``--no-backup`` to skip.
* Validates ``bench_name`` / ``site_name`` via :mod:`utils.validators`, then
  resolves the bench under ``$HOME`` and refuses to operate outside it.
* Requires the user to retype the site name as a typed confirmation (skip via
  ``--yes`` for scripts).
"""

from __future__ import annotations

import os
import shutil

import click
from rich.console import Console

from ..utils.errors import ValidationError
from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner
from ..utils.validators import safe_bench_path, validate_site_name

console = Console()
logger = get_logger("site.delete")


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name under $HOME",
)
@click.option(
    "--site-name",
    prompt="Enter site name (FQDN recommended)",
    default=lambda: os.uname()[1],
    show_default=True,
    help="Site name (FQDN)",
)
@click.option(
    "--no-backup",
    is_flag=True,
    help=("Skip the pre-delete backup. Site deletion is irreversible — use with care."),
)
@click.option(
    "--ignore-errors",
    is_flag=True,
    help="Continue trying to remove the site folder even if `bench drop-site` fails.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the typed-name confirmation (use in scripts).",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.pass_context
def delete(
    ctx: click.Context,
    bench_name: str,
    site_name: str,
    no_backup: bool,
    ignore_errors: bool,
    yes: bool,
    dry_run: bool,
    debug: bool,
) -> None:
    """Delete a Frappe site (drops database and removes site folder).

    Example:

        fp site delete --bench-name mybench --site-name example.com
    """
    try:
        bench_path = safe_bench_path(bench_name)
        site_name = validate_site_name(site_name)
    except ValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if not bench_path.is_dir():
        raise click.ClickException(f"Bench directory '{bench_path}' not found.")

    site_path = bench_path / "sites" / site_name
    if not site_path.is_dir():
        console.print(
            f"[yellow]Site '{site_name}' does not exist in {bench_path}. "
            "Skipping deletion.[/yellow]"
        )
        logger.info(f"[site] Site '{site_name}' does not exist. Skipping.")
        return

    # Make sure we never call rmtree on a path outside the bench.
    try:
        site_path.resolve().relative_to(bench_path.resolve())
    except ValueError as exc:  # pragma: no cover — defensive
        raise click.ClickException(
            f"Refusing to delete: resolved site path escapes bench ({site_path})."
        ) from exc

    console.print(
        f"\n[bold red]About to drop site[/bold red] [cyan]{site_name}[/cyan] "
        f"in [cyan]{bench_path}[/cyan]."
    )
    if no_backup:
        console.print(
            "[yellow]Pre-delete backup will be SKIPPED (--no-backup).[/yellow]"
        )
    else:
        console.print(
            "[dim]A backup will be taken before the database is dropped.[/dim]"
        )

    if not yes and not dry_run:
        typed = click.prompt(
            f"Type the site name '{site_name}' to confirm",
            default="",
            show_default=False,
        )
        if typed != site_name:
            console.print("[yellow]Confirmation mismatch — aborted.[/yellow]")
            raise click.Abort()

    logger.info(f"[site] Deleting site: {site_name} from bench: {bench_path}")

    os.chdir(bench_path)

    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="site.delete"
    )

    drop_cmd = ["bench", "drop-site", site_name]
    if no_backup:
        drop_cmd.append("--no-backup")
    shell_runner.run(
        drop_cmd,
        f"Deleting site '{site_name}'",
        ignore_errors=ignore_errors,
    )

    # Best-effort cleanup: bench drop-site usually removes the folder, but if
    # anything is left behind we tidy up — staying inside the bench tree.
    if site_path.is_dir():
        if dry_run:
            console.print(f"[yellow][dry-run] Would remove folder: {site_path}")
            logger.info(f"[dry-run] Would remove folder: {site_path}")
        else:
            try:
                shutil.rmtree(site_path)
                console.print(f"[green]✓ Site folder '{site_path}' removed.[/green]")
                logger.info(f"[site] Site folder '{site_path}' removed.")
            except Exception as exc:  # noqa: BLE001
                console.print(
                    f"[red]Failed to remove site folder '{site_path}': {exc}[/red]"
                )
                logger.error(
                    f"[site] Failed to remove site folder '{site_path}': {exc}"
                )

    logger.info(f"[site] Site deleted: {site_name}")
    console.print(f"[bold green]✓ Site deleted: {site_name}[/bold green]")
