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
    describe_drop_in,
    disable,
    enable,
    is_enabled,
    is_managed,
    list_nopasswd_supervisorctl_rules,
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
    rules = list_nopasswd_supervisorctl_rules()
    drop_in = describe_drop_in()

    if is_enabled():
        _console.print(
            f"[green]✓[/green] Passwordless [bold]supervisorctl[/bold] is active"
            f"  [dim](user: {user})[/dim]"
        )
        if rules:
            _console.print("  [dim]Active sudo rules:[/dim]")
            for rule in rules:
                _console.print(f"    [cyan]{rule}[/cyan]")
        if drop_in == "managed":
            _console.print(
                f"  [dim]frappe-cli drop-in:[/dim] [green]{SUDOERS_PATH}[/green] "
                "[dim](managed by frappe-cli)[/dim]"
            )
        elif drop_in == "present_other":
            _console.print(
                f"  [dim]frappe-cli path:[/dim] [yellow]{SUDOERS_PATH}[/yellow] "
                "[dim]exists but was not written by frappe-cli[/dim]"
            )
        else:
            _console.print(
                f"  [dim]frappe-cli drop-in:[/dim] [dim]not present at {SUDOERS_PATH}[/dim]"
            )
            if rules:
                _console.print(
                    "  [dim]Passwordless restart is coming from another sudoers "
                    "rule (common after bench setup production).[/dim]"
                )
                _console.print(
                    "  [dim]fp sudo disable-restart only removes the frappe-cli "
                    "file — it cannot remove bench/other rules.[/dim]"
                )
    else:
        _console.print(
            f"[yellow]✗[/yellow] Passwordless [bold]supervisorctl[/bold] is "
            f"[bold]not[/bold] active  [dim](user: {user})[/dim]"
        )
        if drop_in == "managed":
            _console.print(
                f"  [yellow]Note:[/yellow] {SUDOERS_PATH} exists but is not "
                "taking effect — check sudoers syntax with "
                "[cyan]sudo visudo -c[/cyan]."
            )
        elif drop_in == "absent":
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
        if is_enabled():
            _console.print(
                "[dim]  Note: passwordless supervisorctl is already active "
                "via another rule; this adds the frappe-cli drop-in.[/dim]"
            )
        return

    sudo_password = Prompt.ask("  Sudo password", password=True)

    if is_managed(sudo_password):
        _console.print("[green]✓[/green] frappe-cli drop-in already installed.")
        if is_enabled():
            _console.print(
                "  [dim]fp restart and fp deploy will not prompt for a password.[/dim]"
            )
        else:
            _console.print(
                "[yellow]  Passwordless supervisorctl is not active yet — "
                "check other sudoers rules with[/yellow] "
                "[cyan]sudo -l[/cyan]."
            )
        return

    try:
        enable(sudo_password)
        _console.print(
            "[green]✓[/green] frappe-cli sudoers drop-in installed.\n"
            "  [dim]fp restart and fp deploy will not prompt for a password "
            f"({SUDOERS_PATH}).[/dim]"
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
    """Remove the frappe-cli sudoers drop-in only.

    Only removes /etc/sudoers.d/frappe-cli when it was created by frappe-cli.
    If passwordless restart still works afterward, another sudoers rule is
    active (often from bench setup production) — remove that manually.

    \b
    Examples:
        fp sudo disable-restart
        fp sudo disable-restart --dry-run
    """
    if dry_run:
        _console.print(
            f"[dim][dry-run] Would remove {SUDOERS_PATH} "
            "(only if managed by frappe-cli)[/dim]"
        )
        if is_enabled():
            rules = list_nopasswd_supervisorctl_rules()
            if rules:
                _console.print(
                    "[dim]  Passwordless supervisorctl would likely stay active "
                    "via:[/dim]"
                )
                for rule in rules:
                    _console.print(f"[dim]    {rule}[/dim]")
        return

    sudo_password = Prompt.ask("  Sudo password", password=True)

    if not path_exists(sudo_password):
        if is_enabled():
            rules = list_nopasswd_supervisorctl_rules()
            _console.print(
                f"[yellow]No frappe-cli drop-in at {SUDOERS_PATH}.[/yellow]\n"
                "  Passwordless supervisorctl is still active via another rule:"
            )
            for rule in rules or ["  (run [cyan]sudo -l[/cyan] to inspect)"]:
                _console.print(f"    [cyan]{rule}[/cyan]")
            _console.print(
                "\n  [dim]To require a password for fp restart, remove or edit "
                "that rule manually (e.g. [cyan]sudo visudo[/cyan]).[/dim]"
            )
        else:
            _console.print(
                "[dim]No frappe-cli sudoers rule found — nothing to remove.[/dim]"
            )
        return

    if not is_managed(sudo_password):
        raise click.ClickException(
            f"{SUDOERS_PATH} was not created by frappe-cli.\n"
            "  Remove it manually to avoid accidentally deleting a custom rule.\n"
            "  Passwordless supervisorctl may still be enabled by bench or "
            "other sudoers entries — run [cyan]fp sudo status[/cyan]."
        )

    try:
        disable(sudo_password)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    if is_enabled():
        rules = list_nopasswd_supervisorctl_rules()
        _console.print(
            f"[yellow]Removed[/yellow] frappe-cli drop-in: [dim]{SUDOERS_PATH}[/dim]\n"
            "[yellow]Passwordless supervisorctl is still active[/yellow] "
            "via another sudoers rule:"
        )
        for rule in rules or ["  (run [cyan]sudo -l[/cyan] to inspect)"]:
            _console.print(f"    [cyan]{rule}[/cyan]")
        _console.print(
            "\n  [dim]fp sudo disable-restart only manages the frappe-cli file. "
            "To require a password for [cyan]fp restart[/cyan], edit or remove "
            "the rule above (often created by [cyan]bench setup production[/cyan]).[/dim]"
        )
    else:
        _console.print(
            "[green]✓[/green] Passwordless supervisorctl disabled.\n"
            f"  [dim]{SUDOERS_PATH} removed. fp restart will prompt for sudo.[/dim]"
        )
