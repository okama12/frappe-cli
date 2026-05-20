"""``fp sudo`` command group — manage passwordless bench restart.

Commands
--------
fp sudo status          Show whether passwordless fp restart is active.
fp sudo enable-restart  Grant passwordless supervisorctl for this user.
fp sudo disable-restart Remove the sudoers rule (if created by frappe-cli).
"""

from __future__ import annotations

import getpass

import click
from rich.console import Console
from rich.prompt import Prompt

from frappe_cli.utils.sudoers import (
    SUDOERS_PATH,
    disable,
    enable,
    is_enabled,
    is_managed,
    path_exists,
)

_console = Console()


@click.group("sudo")
def sudo_group() -> None:
    """Manage passwordless 'fp restart' (sudoers configuration)."""


@sudo_group.command("status")
def sudo_status() -> None:
    """Show whether passwordless fp restart is active for this user."""
    user = getpass.getuser()

    if is_enabled():
        _console.print(
            f"[green]✓[/green] Passwordless restart is [bold]enabled[/bold]"
            f"  [dim](user: {user})[/dim]"
        )
        if path_exists() and is_managed():
            _console.print(f"  [dim]Managed by frappe-cli → {SUDOERS_PATH}[/dim]")
        else:
            _console.print(
                "  [dim]NOPASSWD rule exists but was not created by frappe-cli[/dim]"
            )
    else:
        _console.print(
            f"[yellow]✗[/yellow] Passwordless restart is [bold]disabled[/bold]"
            f"  [dim](user: {user})[/dim]"
        )
        _console.print("  Run: [cyan]fp sudo enable-restart[/cyan] to enable it.")


@sudo_group.command("enable-restart")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what would happen without making changes.",
)
def enable_restart(dry_run: bool) -> None:
    """Grant passwordless supervisorctl for this user.

    Writes /etc/sudoers.d/frappe-cli and validates it with visudo.
    Requires your sudo password (entered once, not stored).

    \b
    Examples:
        fp sudo enable-restart
        fp sudo enable-restart --dry-run
    """
    if dry_run:
        user = getpass.getuser()
        _console.print(
            f"[dim][dry-run] Would write {SUDOERS_PATH}[/dim]\n"
            f"[dim]  {user} ALL=(ALL) NOPASSWD: <supervisorctl path>[/dim]"
        )
        return

    sudo_password = Prompt.ask("  Sudo password", password=True)

    if is_managed(sudo_password):
        _console.print("[green]✓[/green] Already enabled — nothing to do.")
        return

    try:
        enable(sudo_password)
        _console.print(
            "[green]✓[/green] Passwordless restart enabled.\n"
            "  [dim]fp restart and fp deploy will no longer prompt for a password.[/dim]"
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


@sudo_group.command("disable-restart")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what would happen without making changes.",
)
def disable_restart(dry_run: bool) -> None:
    """Remove the frappe-cli sudoers rule.

    Only removes the drop-in if it was created by frappe-cli.
    Custom sudoers rules are never touched.

    \b
    Examples:
        fp sudo disable-restart
        fp sudo disable-restart --dry-run
    """
    if dry_run:
        _console.print(f"[dim][dry-run] Would remove {SUDOERS_PATH}[/dim]")
        return

    sudo_password = Prompt.ask("  Sudo password", password=True)

    if not path_exists(sudo_password):
        _console.print(
            "[dim]No frappe-cli sudoers rule found — nothing to remove.[/dim]"
        )
        return

    if not is_managed(sudo_password):
        raise click.ClickException(
            f"{SUDOERS_PATH} was not created by frappe-cli.\n"
            "  Remove it manually to avoid accidentally deleting a custom rule."
        )

    try:
        disable(sudo_password)
        _console.print(
            "[green]✓[/green] Passwordless restart disabled.\n"
            f"  [dim]{SUDOERS_PATH} removed.[/dim]"
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
