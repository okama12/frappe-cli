"""``fp sudo`` command group — manage passwordless bench restart.

Commands
--------
fp sudo status          Show whether the frappe-cli drop-in is installed.
fp sudo verify          Run a definitive sudo probe (clears your sudo cache).
fp sudo enable-restart  Grant passwordless supervisorctl for this user.
fp sudo disable-restart Remove the frappe-cli sudoers drop-in.

Design note
-----------
``sudo -n`` succeeds when *either* a NOPASSWD rule exists *or* the user's
sudo timestamp cache is still valid. That ambiguity caused false "passwordless
is active via another rule" messages, so we no longer infer effective state
from it. ``fp sudo status`` reports the deterministic local state of our
drop-in; ``fp sudo verify`` runs the only reliable test (``sudo -k -n``),
which has the side effect of clearing the cache.
"""

from __future__ import annotations

import getpass

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from frappe_cli.utils.sudoers import (
    SUDOERS_PATH,
    clear_local_marker,
    describe_drop_in,
    disable,
    enable,
    has_local_marker,
    is_managed,
    path_exists,
    probe_passwordless,
    write_local_marker,
)

_console = Console()


@click.group("sudo")
def sudo_group() -> None:
    """Manage passwordless 'fp restart' (sudoers configuration)."""


@sudo_group.command("status")
def sudo_status() -> None:
    """Show the state of the frappe-cli sudoers drop-in.

    This reports only what frappe-cli manages. To check whether passwordless
    restart actually works right now (independent of sudo's auth cache), run
    [cyan]fp sudo verify[/cyan].
    """
    user = getpass.getuser()
    drop_in = describe_drop_in()

    _console.print(
        f"[bold]frappe-cli passwordless restart[/bold]  [dim](user: {user})[/dim]"
    )

    if drop_in == "managed":
        _console.print(
            f"  [green]✓[/green] Drop-in installed: [cyan]{SUDOERS_PATH}[/cyan]"
        )
        if has_local_marker() and not path_exists():
            _console.print(
                "    [dim](file is root-only; tracked via ~/.frappe-cli/)[/dim]"
            )
        _console.print(
            "    [dim]→ fp restart and fp deploy will not prompt for a password.[/dim]\n"
            "    [dim]To prove it: [cyan]fp sudo verify[/cyan] "
            "(clears your sudo cache).[/dim]"
        )
    elif drop_in == "present_other":
        _console.print(
            f"  [yellow]![/yellow] {SUDOERS_PATH} exists but was not written by "
            "frappe-cli."
        )
        _console.print(
            "    [dim]Use [cyan]sudo visudo -f /etc/sudoers.d/frappe-cli[/cyan] "
            "to inspect.[/dim]"
        )
    else:
        _console.print("  [yellow]✗[/yellow] Drop-in not installed.")
        _console.print(
            "    Run [cyan]fp sudo enable-restart[/cyan] to enable passwordless "
            "fp restart."
        )
        _console.print(
            "    [dim]Note: if fp restart still works without a password, another "
            "sudoers rule or a recent sudo cache may be responsible.[/dim]"
        )


@sudo_group.command("verify")
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the cache-invalidation warning prompt.",
)
def sudo_verify(yes: bool) -> None:
    """Definitively test whether passwordless supervisorctl is active.

    This runs [cyan]sudo -k -n supervisorctl version[/cyan]. The ``-k`` flag
    invalidates your sudo timestamp cache, so the next sudo command in this
    shell will ask for a password unless a NOPASSWD rule applies.

    Use this when you need a trustworthy answer (e.g. after editing sudoers).
    """
    if not yes:
        _console.print(
            "[yellow]This will clear your sudo timestamp cache[/yellow] so the "
            "test is meaningful."
        )
        if not Confirm.ask("Continue?", default=True):
            _console.print("Cancelled.")
            return

    active, message = probe_passwordless()
    if active:
        _console.print(f"[green]✓[/green] {message}")
    else:
        _console.print(f"[yellow]✗[/yellow] {message}")
        _console.print(
            "    [dim]→ fp restart will prompt for a password. "
            "Run [cyan]fp sudo enable-restart[/cyan] to fix it.[/dim]"
        )


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
        write_local_marker()
        _console.print("[green]✓[/green] frappe-cli drop-in already installed.")
        _console.print(
            "  [dim]Run [cyan]fp sudo verify[/cyan] to confirm it's active "
            "(clears your sudo cache).[/dim]"
        )
        return

    try:
        enable(sudo_password)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    _console.print(
        "[green]✓[/green] frappe-cli sudoers drop-in installed.\n"
        f"  [dim]{SUDOERS_PATH}[/dim]"
    )

    # Self-verify: the only trustworthy proof the rule actually matches sudo's
    # path resolution. Clears the cache; the user just authenticated so the
    # cost is low.
    active, message = probe_passwordless()
    if active:
        _console.print(
            "[green]✓[/green] Verified: fp restart and fp deploy will not prompt "
            "for a password.\n"
            "  [dim]NOPASSWD is now read fresh on every sudo call — "
            "[cyan]sudo -k[/cyan] / [cyan]sudo -K[/cyan] cannot disable it.[/dim]"
        )
    else:
        _console.print(
            "[yellow]![/yellow] Drop-in installed, but sudo did not honour it: "
            f"[dim]{message}[/dim]\n"
            "  [dim]This usually means sudo's secure_path resolves "
            "[cyan]supervisorctl[/cyan] to a different location.\n"
            "  Run [cyan]sudo -ll[/cyan] and [cyan]which supervisorctl[/cyan] "
            "and report the mismatch.[/dim]"
        )


@sudo_group.command("disable-restart")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what would happen without making changes.",
)
def disable_restart(dry_run: bool) -> None:
    """Remove the frappe-cli sudoers drop-in only.

    Only removes /etc/sudoers.d/frappe-cli when it was created by frappe-cli.
    Other sudoers rules are never touched.

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
        return

    sudo_password = Prompt.ask("  Sudo password", password=True)

    if not path_exists(sudo_password):
        if has_local_marker():
            clear_local_marker()
            _console.print(
                "[dim]Drop-in already removed from disk; "
                "cleared local install record.[/dim]"
            )
        else:
            _console.print(
                "[dim]No frappe-cli drop-in found — nothing to remove.[/dim]"
            )
        _console.print(
            "[dim]If fp restart still works without a password, run "
            "[cyan]fp sudo verify[/cyan] for the real state, then inspect "
            "[cyan]sudo visudo[/cyan].[/dim]"
        )
        return

    if not is_managed(sudo_password):
        raise click.ClickException(
            f"{SUDOERS_PATH} was not created by frappe-cli.\n"
            "  Remove it manually to avoid deleting an unrelated rule."
        )

    try:
        disable(sudo_password)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    _console.print(
        f"[green]✓[/green] Removed [cyan]{SUDOERS_PATH}[/cyan].\n"
        "  [dim]Your sudo timestamp cache may still allow fp restart for a few "
        "minutes — run [cyan]sudo -k && fp sudo verify[/cyan] to confirm.[/dim]"
    )
