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


# ── NodeJSStep ────────────────────────────────────────────────────────────────

class TestNodeJSStep:
    def test_check_true_when_node_present(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert NodeJSStep().check(make_ctx()) is True

    def test_check_false_when_node_missing(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert NodeJSStep().check(make_ctx()) is False

    def test_run_uses_node18_for_2204(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        ctx = make_ctx(ubuntu_version="22.04")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            NodeJSStep().run(ctx)
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "18" in all_args

    def test_run_uses_node20_for_2404(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        ctx = make_ctx(ubuntu_version="24.04")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            NodeJSStep().run(ctx)
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "20" in all_args


# ── MariaDB ───────────────────────────────────────────────────────────────────

class TestMariaDBInstallStep:
    def test_check_true_when_running_and_config_exists(self, tmp_path):
        from frappe_cli.install.steps.mariadb import MariaDBInstallStep
        step = MariaDBInstallStep()
        fake_cnf = tmp_path / "99-frappe.cnf"
        fake_cnf.write_text("[mysqld]")
        with patch("subprocess.run") as mock_run, \
             patch.object(step, "CNF_PATH", str(fake_cnf)):
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_false_when_mysqladmin_fails(self):
        from frappe_cli.install.steps.mariadb import MariaDBInstallStep
        step = MariaDBInstallStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False


class TestMariaDBSecureStep:
    def test_check_true_when_password_auth_works(self):
        from frappe_cli.install.steps.mariadb import MariaDBSecureStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert MariaDBSecureStep().check(make_ctx()) is True

    def test_check_false_when_auth_fails(self):
        from frappe_cli.install.steps.mariadb import MariaDBSecureStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert MariaDBSecureStep().check(make_ctx()) is False


# ── RedisStep ─────────────────────────────────────────────────────────────────

class TestRedisStep:
    def test_check_true_when_ping_returns_pong(self):
        from frappe_cli.install.steps.redis import RedisStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="PONG\n")
            assert RedisStep().check(make_ctx()) is True

    def test_check_false_when_ping_fails(self):
        from frappe_cli.install.steps.redis import RedisStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert RedisStep().check(make_ctx()) is False
