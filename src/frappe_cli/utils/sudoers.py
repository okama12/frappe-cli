"""Shared helpers for writing/removing the frappe-cli sudoers drop-in.

The drop-in grants the current Linux user passwordless ``sudo`` access to
``supervisorctl`` only — the minimal privilege needed by ``bench restart``
(and therefore ``fp restart`` / ``fp deploy``).

File managed: ``/etc/sudoers.d/frappe-cli``

Safety rules this module enforces:
- Always validate with ``visudo -c`` before installing.
- Never overwrite a drop-in that was NOT written by this tool (header check).
- Scope to one user + one binary (least privilege).
- Read root-owned drop-ins via ``sudo cat`` (mode 0440 is not user-readable).
"""

from __future__ import annotations

import getpass
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

SUDOERS_PATH = Path("/etc/sudoers.d/frappe-cli")
_MANAGED_MARKER = "# Managed by frappe-cli"
_LOCAL_STATE = Path.home() / ".frappe-cli" / "passwordless-restart.json"


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


def path_exists(sudo_password: str | None = None) -> bool:
    """Public alias for sudo-aware existence check."""
    return _path_exists(sudo_password)


def _path_exists(sudo_password: str | None = None) -> bool:
    """Robustly check if SUDOERS_PATH exists.

    ``/etc/sudoers.d/`` is mode 0750 root:root on Ubuntu/Debian, so a
    non-root user gets ``PermissionError`` from ``Path.exists()`` (Python 3.12+).
    Fall back to ``sudo -S test -e`` whenever the direct check fails.
    """
    try:
        return SUDOERS_PATH.exists()
    except OSError:
        pass
    if not sudo_password:
        return False
    result = subprocess.run(
        ["sudo", "-S", "test", "-e", str(SUDOERS_PATH)],
        input=(sudo_password + "\n").encode(),
        capture_output=True,
    )
    return result.returncode == 0


def _read_drop_in_content(sudo_password: str | None = None) -> str | None:
    """Return drop-in text, or None if the file is missing or unreadable."""
    if not _path_exists(sudo_password):
        return None
    try:
        return SUDOERS_PATH.read_text(encoding="utf-8")
    except PermissionError:
        pass
    except OSError:
        return None
    if not sudo_password:
        return None
    result = subprocess.run(
        ["sudo", "-S", "cat", str(SUDOERS_PATH)],
        input=(sudo_password + "\n").encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    out = result.stdout
    if isinstance(out, bytes):
        return out.decode(errors="replace")
    return out or None


def is_managed(sudo_password: str | None = None) -> bool:
    """Return True when the drop-in exists and was written by frappe-cli."""
    content = _read_drop_in_content(sudo_password)
    if content is None:
        return False
    return content.lstrip().startswith(_MANAGED_MARKER)


def is_enabled() -> bool:
    """Return True when passwordless supervisorctl is currently active."""
    result = subprocess.run(
        ["sudo", "-n", "supervisorctl", "version"],
        capture_output=True,
    )
    return result.returncode == 0


def _expected_rule_line(user: str | None = None) -> str:
    user = user or getpass.getuser()
    return f"{user} ALL=(ALL) NOPASSWD: {_supervisorctl_path()}"


def write_local_marker() -> None:
    """Record that frappe-cli installed the drop-in (for status on 0750 sudoers.d)."""
    _LOCAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "drop_in": str(SUDOERS_PATH),
        "user": getpass.getuser(),
        "supervisorctl": _supervisorctl_path(),
        "rule": _expected_rule_line(),
    }
    _LOCAL_STATE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def clear_local_marker() -> None:
    """Remove local install record."""
    _LOCAL_STATE.unlink(missing_ok=True)


def has_local_marker() -> bool:
    """True when frappe-cli previously installed the drop-in on this machine."""
    if not _LOCAL_STATE.exists():
        return False
    try:
        data = json.loads(_LOCAL_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("user") == getpass.getuser() and data.get("drop_in") == str(
        SUDOERS_PATH
    )


def rule_matches_frappe_install(rule: str) -> bool:
    """True when a sudo -l line matches what frappe-cli writes."""
    low = rule.lower()
    user = getpass.getuser().lower()
    binary = _supervisorctl_path().lower()
    return user in low and binary in low and "nopasswd" in low


def list_nopasswd_supervisorctl_rules() -> list[str]:
    """Return ``sudo -l`` lines that grant passwordless supervisorctl."""
    result = subprocess.run(
        ["sudo", "-n", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    rules: list[str] = []
    for line in result.stdout.splitlines():
        low = line.lower()
        if "supervisorctl" in low and ("nopasswd" in low or "may run" in low):
            rules.append(line.strip())
    return rules


def describe_drop_in(sudo_password: str | None = None) -> str:
    """Human-readable state of the frappe-cli drop-in file.

    Returns one of: ``managed``, ``present_other``, ``absent``.

    On Ubuntu/Debian ``/etc/sudoers.d/`` is mode 0750, so checks without a
    sudo password often cannot stat the file. We fall back to the local marker
    frappe-cli writes on ``enable``, and to ``sudo -l`` when passwordless
    supervisorctl is already active.
    """
    if _path_exists(sudo_password):
        if is_managed(sudo_password):
            return "managed"
        return "present_other"

    if has_local_marker():
        return "managed"

    if is_enabled():
        rules = list_nopasswd_supervisorctl_rules()
        if any(rule_matches_frappe_install(r) for r in rules):
            return "managed"

    return "absent"


def enable(sudo_password: str, *, dry_run: bool = False) -> None:
    """Write the drop-in and validate with visudo.

    Raises ``RuntimeError`` if:
    - ``visudo -c`` rejects the file
    - The existing drop-in was not created by this tool (to avoid overwriting)
    - The drop-in exists but cannot be read even with sudo
    """
    if dry_run:
        return

    if is_managed(sudo_password):
        return

    if _path_exists(sudo_password):
        content = _read_drop_in_content(sudo_password)
        if content is None:
            raise RuntimeError(
                f"Cannot read {SUDOERS_PATH} (sudo failed or wrong password).\n"
                "  Re-enter your sudo password and try again."
            )
        if not content.lstrip().startswith(_MANAGED_MARKER):
            raise RuntimeError(
                f"{SUDOERS_PATH} already exists but was not created by frappe-cli.\n"
                "  Edit it manually or remove it first."
            )

    user = getpass.getuser()
    content = _drop_in_content(user)

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
        write_local_marker()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def disable(sudo_password: str, *, dry_run: bool = False) -> None:
    """Remove the drop-in, but only if it was written by this tool.

    Raises ``RuntimeError`` if the file exists but is not managed by frappe-cli.
    """
    if not _path_exists(sudo_password):
        return  # Nothing to do.

    if not is_managed(sudo_password):
        raise RuntimeError(
            f"{SUDOERS_PATH} was not created by frappe-cli.\n"
            "  Remove it manually to avoid accidentally deleting a custom rule."
        )

    if dry_run:
        return

    _sudo_run(["rm", "-f", str(SUDOERS_PATH)], sudo_password)
    clear_local_marker()


def _sudo_run(cmd: list[str], sudo_password: str) -> None:
    """Run a command with sudo -S, raising RuntimeError on failure."""
    result = subprocess.run(
        ["sudo", "-S"] + cmd,
        input=(sudo_password + "\n").encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: sudo {' '.join(cmd)}\n"
            + result.stderr.decode(errors="replace")
        )
