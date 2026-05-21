import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

STATE_FILE = Path.home() / ".frappe-cli-state.json"


@dataclass
class InstallState:
    bench_name: str = ""
    site_name: str = ""
    frappe_branch: str = ""
    app_url: str = ""
    app_branch: str = ""
    ssl_email: str = ""
    ubuntu_version: str = ""
    enable_passwordless_restart: bool = False
    completed_steps: list[str] = field(default_factory=list)


def save_state(state: InstallState) -> None:
    """Persist install progress to ``~/.frappe-cli-state.json`` (mode 0600).

    No passwords are stored — only completed-step names, bench/site identifiers,
    and the user's choice for passwordless-restart. We still enforce 0600 because
    on a multi-user box other users have no business reading another user's
    install plan.
    """
    payload = json.dumps(asdict(state), indent=2)
    # Write atomically: write to a temp neighbour, fsync, then rename + chmod.
    tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, STATE_FILE)
        os.chmod(STATE_FILE, 0o600)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def load_state() -> InstallState:
    if not STATE_FILE.exists():
        return InstallState()
    data = json.loads(STATE_FILE.read_text())
    return InstallState(**data)


def clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def state_exists() -> bool:
    return STATE_FILE.exists()
