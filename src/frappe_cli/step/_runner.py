"""Shared helpers for the `fp step` group.

Builds a minimal `InstallContext` from CLI flags, runs `step.check(ctx)`
to short-circuit when work is already done, and executes `step.run(ctx)`
with a live log callback that streams output to the Rich console.

Sudo password is collected once via `getpass` only when the step actually
needs sudo (kept on `InstallContext.sudo_password`). Steps that don't
shell out via `_sudo()` (`DnsMultitenantStep`, `AppGetStep`, etc.) skip
the prompt entirely.
"""

from __future__ import annotations

import getpass
import platform
from typing import Optional

import click
from rich.console import Console

from frappe_cli.install.context import InstallContext
from frappe_cli.install.steps.base import InstallStep, StepError

console = Console()


def _detect_ubuntu_version() -> str:
    """Best-effort Ubuntu version detection (matches install wizard)."""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    try:
        return platform.freedesktop_os_release().get("VERSION_ID", "22.04")
    except (AttributeError, OSError):
        return "22.04"


def build_context(
    *,
    bench_name: str = "",
    site_name: str = "",
    frappe_branch: str = "version-15",
    app_url: str = "",
    app_branch: str = "version-15",
    mariadb_root_password: str = "",
    admin_password: str = "",
    ssl_email: str = "",
    dry_run: bool = False,
    debug: bool = False,
    needs_sudo: bool = True,
    sudo_password: Optional[str] = None,
) -> InstallContext:
    """Construct an `InstallContext` for a single-step run.

    Unset fields default to empty strings; each step only consumes the
    fields it cares about, so callers only need to pass what's relevant.

    The log callback prints lines verbatim with the `[dim]` Rich style so
    streamed subprocess output is visually distinguished from CLI status
    messages.
    """

    def _log(line: str) -> None:
        console.print(f"[dim]{line}[/dim]")

    if needs_sudo and sudo_password is None and not dry_run:
        sudo_password = getpass.getpass("Sudo password: ")
    sudo_password = sudo_password or ""

    return InstallContext(
        bench_name=bench_name,
        site_name=site_name,
        frappe_branch=frappe_branch,
        app_url=app_url,
        app_branch=app_branch,
        sudo_password=sudo_password,
        mariadb_root_password=mariadb_root_password,
        admin_password=admin_password,
        ssl_email=ssl_email,
        ubuntu_version=_detect_ubuntu_version(),
        dry_run=dry_run,
        debug=debug,
        log_fn=_log,
    )


def run_step(step: InstallStep, ctx: InstallContext, *, force: bool = False) -> None:
    """Run one `InstallStep` end-to-end with friendly CLI output.

    1. Print a banner.
    2. Call `step.check(ctx)`. If True and not --force, exit "[already done]".
    3. Call `step.run(ctx)`, streaming output via `ctx.log_fn`.
    4. On `StepError`, raise a `click.ClickException` with the hint.
    """
    console.print(
        f"\n[bold cyan]→ {step.name}[/bold cyan]  [dim]({step.description})[/dim]"
    )

    if ctx.dry_run:
        console.print(
            "[yellow]\\[dry-run][/yellow] commands will be printed, not executed."
        )

    try:
        already = step.check(ctx)
    except Exception as e:  # noqa: BLE001 — check() must never crash the CLI
        console.print(f"[yellow]check() raised:[/yellow] {e}; continuing.")
        already = False

    if already and not force:
        console.print(
            f"[green]✓ {step.name} already complete — use --force to rerun.[/green]"
        )
        return

    try:
        step.run(ctx)
    except StepError as e:
        msg = e.message
        if e.hint:
            msg = f"{msg}\n  hint: {e.hint}"
        raise click.ClickException(msg)

    console.print(f"[bold green]✓ {step.name} complete[/bold green]")
