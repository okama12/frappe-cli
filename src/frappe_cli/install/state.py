import json
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
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2))


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
