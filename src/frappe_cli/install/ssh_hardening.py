"""``fp install ssh-hardening`` — disable root login + password auth in sshd.

Locking yourself out is the #1 risk here. Before disabling password auth we:

* Insist that an SSH key is configured for the invoking user
  (``~/.ssh/authorized_keys`` exists and is non-empty), unless the user
  passes ``--force``.
* Run ``sshd -t`` after editing to verify the config still parses; if not,
  we restore the pre-edit backup and refuse to restart sshd.

The original implementation called ``sudo sed -i`` directly on ``sshd_config``
with no validation and no rollback — a typo there could brick remote access.
"""

from __future__ import annotations

import datetime
import os
import subprocess
from pathlib import Path

import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("install.ssh_hardening")

SSHD_CONFIG = Path("/etc/ssh/sshd_config")


def _user_has_authorized_keys() -> bool:
    """Return True if the invoking user has a non-empty ``authorized_keys``."""
    home = Path(os.path.expanduser("~"))
    keys = home / ".ssh" / "authorized_keys"
    try:
        return keys.is_file() and keys.stat().st_size > 0
    except OSError:
        return False


def _backup_sshd_config() -> Path:
    """Copy sshd_config to /etc with a timestamped suffix; return new path."""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = SSHD_CONFIG.with_name(f"sshd_config.bak.{ts}")
    subprocess.run(["sudo", "cp", "-a", str(SSHD_CONFIG), str(backup)], check=True)
    return backup


def _validate_sshd_config() -> tuple[bool, str]:
    proc = subprocess.run(
        ["sudo", "sshd", "-t"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, proc.stderr.strip()


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help=(
        "Apply hardening even when no SSH key is detected for the current user. "
        "Only pass this if you have console access — once password auth is off, "
        "an SSH key is the ONLY way back in."
    ),
)
@click.pass_context
def ssh_hardening(ctx: click.Context, force: bool) -> None:
    """Disable root login and password-only SSH auth (with safety guards)."""
    if not _user_has_authorized_keys() and not force:
        raise click.ClickException(
            "No ~/.ssh/authorized_keys found for this user. "
            "Add your public key first, or pass --force if you have an "
            "alternative way back in (console, IPMI). "
            "Disabling password auth without a key would lock you out."
        )

    logger.info("[ssh_hardening] Applying SSH security best practices...")
    if not SSHD_CONFIG.exists():
        raise click.ClickException(f"{SSHD_CONFIG} not found")

    backup = _backup_sshd_config()
    console.print(f"[dim]Backed up sshd_config to {backup}[/dim]")

    # In-place edits (PermitRootLogin no, PasswordAuthentication no).
    subprocess.run(
        [
            "sudo",
            "sed",
            "-i",
            "s/^[#[:space:]]*PermitRootLogin.*/PermitRootLogin no/",
            str(SSHD_CONFIG),
        ],
        check=True,
    )
    subprocess.run(
        [
            "sudo",
            "sed",
            "-i",
            "s/^[#[:space:]]*PasswordAuthentication.*/PasswordAuthentication no/",
            str(SSHD_CONFIG),
        ],
        check=True,
    )

    ok, err = _validate_sshd_config()
    if not ok:
        console.print(f"[red]sshd -t failed:[/red]\n{err}")
        console.print("[yellow]Restoring previous sshd_config…[/yellow]")
        subprocess.run(
            ["sudo", "cp", "-a", str(backup), str(SSHD_CONFIG)],
            check=True,
        )
        raise click.ClickException(
            "sshd config validation failed after edit; backup restored. "
            "No restart performed."
        )

    # Restart sshd via whichever unit is active.
    for unit in ("ssh", "sshd"):
        try:
            subprocess.run(
                ["sudo", "systemctl", "restart", unit], check=True, capture_output=True
            )
            break
        except subprocess.CalledProcessError:
            continue
    else:
        raise click.ClickException(
            "Could not restart ssh/sshd. Inspect manually — the config edit "
            "succeeded but the daemon was not reloaded."
        )

    click.secho(
        "SSH hardening applied: root login and password auth disabled.", fg="green"
    )
    logger.info("[ssh_hardening] SSH hardening applied. Backup at %s", backup)
