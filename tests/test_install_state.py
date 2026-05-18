import json
from pathlib import Path
import pytest
from frappe_cli.install.state import (
    InstallState, save_state, load_state, clear_state, state_exists, STATE_FILE
)


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    fake_state = tmp_path / ".frappe-cli-state.json"
    monkeypatch.setattr("frappe_cli.install.state.STATE_FILE", fake_state)
    yield fake_state
    if fake_state.exists():
        fake_state.unlink()


def test_state_does_not_exist_initially(clean_state):
    assert not state_exists()


def test_save_and_load_roundtrip(clean_state):
    state = InstallState(
        bench_name="frappe-bench",
        site_name="mysite.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15",
        ssl_email="admin@mysite.com",
        ubuntu_version="22.04",
        completed_steps=["system_update", "system_deps"],
    )
    save_state(state)
    loaded = load_state()
    assert loaded.bench_name == "frappe-bench"
    assert loaded.completed_steps == ["system_update", "system_deps"]


def test_save_creates_file(clean_state):
    save_state(InstallState(bench_name="b", site_name="s.com", frappe_branch="v15",
                            app_url="u", app_branch="v15", ssl_email="e@e.com",
                            ubuntu_version="22.04", completed_steps=[]))
    assert state_exists()


def test_clear_removes_file(clean_state):
    save_state(InstallState(bench_name="b", site_name="s.com", frappe_branch="v15",
                            app_url="u", app_branch="v15", ssl_email="e@e.com",
                            ubuntu_version="22.04", completed_steps=[]))
    clear_state()
    assert not state_exists()


def test_passwords_not_in_state(clean_state):
    state = InstallState(bench_name="b", site_name="s.com", frappe_branch="v15",
                         app_url="u", app_branch="v15", ssl_email="e@e.com",
                         ubuntu_version="22.04", completed_steps=[])
    save_state(state)
    raw = clean_state.read_text()
    assert "sudo_password" not in raw
    assert "mariadb_root_password" not in raw
    assert "admin_password" not in raw


def test_load_returns_empty_state_when_file_missing(clean_state):
    loaded = load_state()
    assert loaded.bench_name == ""
    assert loaded.completed_steps == []
