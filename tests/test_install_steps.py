# tests/test_install_steps.py
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from frappe_cli.install.context import InstallContext
from frappe_cli.install.steps.base import StepError


def make_ctx(**overrides):
    defaults = dict(
        bench_name="frappe-bench", site_name="mysite.com",
        frappe_branch="version-15", app_url="https://github.com/frappe/erpnext",
        app_branch="version-15", sudo_password="secret",
        mariadb_root_password="dbpass", admin_password="adminpass",
        ssl_email="admin@mysite.com", ubuntu_version="22.04",
        dry_run=False, debug=False,
    )
    defaults.update(overrides)
    return InstallContext(**defaults)


# ── SystemUpdateStep ──────────────────────────────────────────────────────────

class TestSystemUpdateStep:
    def test_check_always_returns_false(self):
        from frappe_cli.install.steps.system import SystemUpdateStep
        step = SystemUpdateStep()
        assert step.check(make_ctx()) is False

    def test_run_calls_apt_update_and_upgrade(self):
        from frappe_cli.install.steps.system import SystemUpdateStep
        step = SystemUpdateStep()
        ctx = make_ctx()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            step.run(ctx)
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("apt-get" in c and "update" in c for c in calls)
        assert any("apt-get" in c and "upgrade" in c for c in calls)

    def test_dry_run_does_not_call_subprocess(self):
        from frappe_cli.install.steps.system import SystemUpdateStep
        step = SystemUpdateStep()
        ctx = make_ctx(dry_run=True)
        with patch("subprocess.run") as mock_run:
            step.run(ctx)
        mock_run.assert_not_called()


# ── SystemDepsStep ────────────────────────────────────────────────────────────

class TestSystemDepsStep:
    def test_check_returns_true_when_all_packages_present(self):
        from frappe_cli.install.steps.system import SystemDepsStep
        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_returns_false_when_package_missing(self):
        from frappe_cli.install.steps.system import SystemDepsStep
        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False

    def test_run_installs_required_packages(self):
        from frappe_cli.install.steps.system import SystemDepsStep, SYSTEM_PACKAGES
        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            step.run(make_ctx())
        all_args = [str(a) for c in mock_run.call_args_list for a in c.args[0]]
        for pkg in SYSTEM_PACKAGES:
            assert pkg in all_args


# ── UvCheckStep ───────────────────────────────────────────────────────────────

class TestUvCheckStep:
    def test_check_returns_true_when_uv_installed(self):
        from frappe_cli.install.steps.uv_check import UvCheckStep
        step = UvCheckStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_returns_false_when_uv_missing(self):
        from frappe_cli.install.steps.uv_check import UvCheckStep
        step = UvCheckStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False
