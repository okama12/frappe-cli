"""Dev-workflow Click commands added to the ``fp`` entry point.

Commands
--------
use <site>   Set the active site for the current bench (writes .fp.yaml).
context      Show the current bench root and active site.
sites        List all sites in the current bench.

Passthrough commands (thin wrappers around ``bench``):
  migrate, console, restart, build, start, get-app, watch,
  install-app, uninstall-app, list-apps, clear-cache, mariadb

deploy       git pull → migrate → restart (daily deploy workflow)

Each passthrough resolves the bench root from the current working directory
and injects ``--site <active_site>`` automatically for site-scoped commands.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from frappe_cli.dev.context import (
    find_bench_root,
    list_sites,
    read_active_site,
    site_exists,
    write_active_site,
)

_console = Console()

# Commands that require --site <site> to be prepended.
SITE_REQUIRED: set[str] = {
    "migrate",
    "console",
    "install-app",
    "uninstall-app",
    "list-apps",
    "backup",
    "restore",
    "execute",
    "clear-cache",
    "set-config",
    "show-config",
    "mariadb",
    "browse",
    "set-admin-password",
    "set-password",
}


def _require_bench() -> Path:
    """Return the bench root or abort with a helpful message."""
    root = find_bench_root(Path(os.getcwd()))
    if root is None:
        raise click.ClickException(
            "Not inside a Frappe bench directory.\n"
            "  cd into your bench (or any subdirectory) and try again.\n"
            "  Tip: use 'fp install wizard' to create a new bench."
        )
    return root


def _require_site(bench_root: Path) -> str:
    """Return the active site name or abort with a helpful message."""
    site = read_active_site(bench_root)
    if not site:
        raise click.ClickException(
            f"No active site set for bench '{bench_root.name}'.\n"
            "  Run: fp use <site-name>"
        )
    return site


def _is_git_repo(path: Path) -> bool:
    """Return True when *path* is inside a git work tree."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _run_checked(cmd: list[str], *, cwd: Path, label: str) -> None:
    """Run *cmd* in *cwd*; exit with its code on failure."""
    _console.print(f"[bold cyan]→[/bold cyan] {label}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


# ── fp use ────────────────────────────────────────────────────────────────────


@click.command("use")
@click.argument("site")
def use(site: str) -> None:
    """Set the active site for the current bench.

    Works from any directory inside a bench (bench root, apps/, apps/my_app,
    sites/, etc.).  The chosen site is saved in .fp.yaml at the bench root.

    \b
    Examples:
        fp use test7.rashidiokama.com
        fp use dev.local
    """
    bench_root = _require_bench()

    if not site_exists(bench_root, site):
        available = list_sites(bench_root)
        hint = (
            ("  Available: " + ", ".join(available))
            if available
            else "  No sites found."
        )
        raise click.ClickException(
            f"Site '{site}' not found in bench '{bench_root.name}'.\n{hint}"
        )

    write_active_site(bench_root, site)
    _console.print(
        f"[green]✓[/green] Active site set to [bold]{site}[/bold]"
        f"  [dim](bench: {bench_root.name})[/dim]"
    )


# ── fp context ────────────────────────────────────────────────────────────────


@click.command("context")
def context() -> None:
    """Show the current bench and active site."""
    bench_root = find_bench_root(Path(os.getcwd()))

    if bench_root is None:
        _console.print(
            "[yellow]Not inside a bench.[/yellow]  "
            "cd into your bench directory first."
        )
        return

    active_site = read_active_site(bench_root)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value", style="bold")
    table.add_row("Bench", str(bench_root))
    if active_site:
        table.add_row("Site", active_site)
    else:
        table.add_row("Site", "[yellow]not set — run: fp use <site>[/yellow]")
    _console.print(table)


# ── fp sites ──────────────────────────────────────────────────────────────────


@click.command("sites")
def sites() -> None:
    """List all sites in the current bench."""
    bench_root = _require_bench()
    found = list_sites(bench_root)
    active = read_active_site(bench_root)

    if not found:
        _console.print("[yellow]No sites found[/yellow] in this bench.")
        return

    for s in found:
        marker = "[green]●[/green]" if s == active else " "
        _console.print(f"  {marker} {s}")

    if active:
        _console.print(f"\n[dim]Active site:[/dim] [bold]{active}[/bold]")
    else:
        _console.print("\n[dim]No active site. Run:[/dim] fp use <site>")


# ── fp deploy ─────────────────────────────────────────────────────────────────


@click.command("deploy")
@click.option(
    "--no-pull",
    is_flag=True,
    help="Skip git pull (migrate + restart only).",
)
def deploy(no_pull: bool) -> None:
    """Pull latest code, migrate the active site, then restart bench.

    Runs in order: git pull → bench migrate → bench restart.
    Migrate runs before restart so schema/code changes apply cleanly.

    Run from an app directory (e.g. apps/my_app) to pull that repo.
    Migrate and restart always run from the detected bench root.

    \b
    Examples:
        cd ~/my-bench/apps/my_app && fp deploy
        fp deploy --no-pull
    """
    bench_root = _require_bench()
    site = _require_site(bench_root)
    cwd = Path(os.getcwd())

    if not no_pull:
        if not _is_git_repo(cwd):
            raise click.ClickException(
                "Not inside a git repository.\n"
                "  cd into the app you want to pull, or use --no-pull."
            )
        _run_checked(["git", "pull"], cwd=cwd, label="git pull")

    _run_checked(
        ["bench", "--site", site, "migrate"],
        cwd=bench_root,
        label=f"migrate {site}",
    )
    _run_checked(["bench", "restart"], cwd=bench_root, label="restart bench")
    _console.print("[green]✓[/green] Deploy complete")


# ── passthrough factory ───────────────────────────────────────────────────────


def _make_passthrough(
    name: str,
    *,
    needs_site: Optional[bool] = None,
    help_text: str = "",
) -> click.Command:
    """Return a Click command that passes through to ``bench <name>``.

    If *needs_site* is ``None`` the function consults ``SITE_REQUIRED``.
    Extra arguments/options are forwarded verbatim.
    """
    site_scoped: bool = (name in SITE_REQUIRED) if needs_site is None else needs_site

    @click.command(
        name,
        help=help_text or f"Run 'bench {name}' in the current bench.",
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    @click.argument("extra_args", nargs=-1, type=click.UNPROCESSED)
    def _cmd(extra_args: tuple[str, ...]) -> None:
        bench_root = _require_bench()

        cmd: list[str] = ["bench"]

        if site_scoped:
            site = _require_site(bench_root)
            cmd += ["--site", site]

        cmd += [name, *extra_args]

        result = subprocess.run(cmd, cwd=str(bench_root))
        raise SystemExit(result.returncode)

    return _cmd


# ── Tier 1 passthrough commands ───────────────────────────────────────────────

migrate = _make_passthrough(
    "migrate",
    help_text="Run patches, sync schema, and rebuild files/translations for the active site.",
)
console = _make_passthrough(
    "console",
    help_text="Open an IPython console for the active site.",
)
restart = _make_passthrough(
    "restart",
    needs_site=False,
    help_text="Restart bench processes (supervisor/systemd).",
)
build = _make_passthrough(
    "build",
    needs_site=False,
    help_text="Build JS and CSS assets for the bench.",
)
start = _make_passthrough(
    "start",
    needs_site=False,
    help_text="Start bench development processes (Procfile).",
)
watch = _make_passthrough(
    "watch",
    needs_site=False,
    help_text="Watch and recompile JS/CSS as files change.",
)
get_app = _make_passthrough(
    "get-app",
    needs_site=False,
    help_text="Download and install a Frappe app from a git URL.",
)
install_app = _make_passthrough(
    "install-app",
    help_text="Install an app on the active site.",
)
uninstall_app = _make_passthrough(
    "uninstall-app",
    help_text="Uninstall an app from the active site.",
)
list_apps_cmd = _make_passthrough(
    "list-apps",
    help_text="List apps installed on the active site.",
)
clear_cache = _make_passthrough(
    "clear-cache",
    help_text="Clear cache for the active site.",
)
bench_mariadb = _make_passthrough(
    "mariadb",
    help_text="Open the MariaDB console for the active site.",
)

# Exported for registration in cli.py
ALL_DEV_COMMANDS: list[click.Command] = [
    use,
    context,
    sites,
    deploy,
    migrate,
    console,
    restart,
    build,
    start,
    watch,
    get_app,
    install_app,
    uninstall_app,
    list_apps_cmd,
    clear_cache,
    bench_mariadb,
]
