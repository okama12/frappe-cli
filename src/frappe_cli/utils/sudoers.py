"""Shared helpers for writing/removing the frappe-cli sudoers drop-in.

The drop-in grants the current Linux user passwordless ``sudo`` access to
``supervisorctl`` only — the minimal privilege needed by ``bench restart``
(and therefore ``fp restart`` / ``fp deploy``).

File managed: ``/etc/sudoers.d/frappe-cli``

Safety rules this module enforces:
- Always validate with ``visudo -c`` before installing.
- Never overwrite a drop-in that was NOT written by this tool (header check).
- Scope to one user + one binary (least privilege).
"""

from __future__ import annotations

import getpass
import shutil
import subprocess
import tempfile
from pathlib import Path

SUDOERS_PATH = Path("/etc/sudoers.d/frappe-cli")
_MANAGED_MARKER = "# Managed by frappe-cli"


def _supervisorctl_path() -> str:
    """Return the absolute path to supervisorctl, or a safe default."""
    found = shutil.which("supervisorctl")
    return found or "/usr/bin/supervisorctl"


def _drop_in_content(user: str) -> str:
    binary = _supervisorctl_path()
    return (
        f"{_MANAGED_MARKER}\n"
        f"# Remove with: fp sudo disable-restart\n"
        f"{user} ALL=(ALL) NOPASSWD: {binary}\n"
    )


def is_managed() -> bool:
    """Return True when the drop-in exists and was written by frappe-cli."""
    try:
        return SUDOERS_PATH.read_text().startswith(_MANAGED_MARKER)
    except OSError:
        return False


def is_enabled() -> bool:
    """Return True when passwordless supervisorctl is currently active."""
    result = subprocess.run(
        ["sudo", "-n", "supervisorctl", "version"],
        capture_output=True,
    )
    return result.returncode == 0


def enable(sudo_password: str, *, dry_run: bool = False) -> None:
    """Write the drop-in and validate with visudo.

    Raises ``RuntimeError`` if:
    - ``visudo -c`` rejects the file
    - The existing drop-in was not created by this tool (to avoid overwriting)
    """
    if SUDOERS_PATH.exists() and not is_managed():
        raise RuntimeError(
            f"{SUDOERS_PATH} already exists but was not created by frappe-cli.\n"
            "  Edit it manually or remove it first."
        )

    user = getpass.getuser()
    content = _drop_in_content(user)

    if dry_run:
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sudoers", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Validate syntax before installing.
        result = subprocess.run(
            ["sudo", "-S", "visudo", "-cf", tmp_path],
            input=(sudo_password + "\n").encode(),
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "visudo rejected the sudoers file:\n"
                + result.stderr.decode(errors="replace")
            )

        # Install with correct permissions (0440, root:root).
        _sudo_run(
            [
                "install",
                "-m",
                "0440",
                "-o",
                "root",
                "-g",
                "root",
                tmp_path,
                str(SUDOERS_PATH),
            ],
            sudo_password,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def disable(sudo_password: str, *, dry_run: bool = False) -> None:
    """Remove the drop-in, but only if it was written by this tool.

    Raises ``RuntimeError`` if the file exists but is not managed by frappe-cli.
    """
    if not SUDOERS_PATH.exists():
        return  # Nothing to do.

    if not is_managed():
        raise RuntimeError(
            f"{SUDOERS_PATH} was not created by frappe-cli.\n"
            "  Remove it manually to avoid accidentally deleting a custom rule."
        )

    if dry_run:
        return

    _sudo_run(["rm", str(SUDOERS_PATH)], sudo_password)


def _sudo_run(cmd: list[str], sudo_password: str) -> None:
    """Run a command with sudo -S, raising RuntimeError on failure."""
    result = subprocess.run(
        ["sudo", "-S"] + cmd,
        input=(sudo_password + "\n").encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            + result.stderr.decode(errors="replace")
        )
