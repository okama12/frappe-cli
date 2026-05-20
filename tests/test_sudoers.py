"""Tests for sudoers util, SudoersSetupStep, and fp sudo commands."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from frappe_cli.cli import cli
from frappe_cli.install.context import InstallContext

# ── helpers ───────────────────────────────────────────────────────────────────


def make_ctx(**overrides):
    defaults = dict(
        bench_name="test-bench",
        site_name="dev.local",
        frappe_branch="version-15",
        app_url="",
        app_branch="version-15",
        sudo_password="secret",
        mariadb_root_password="dbpass",
        admin_password="adminpass",
        ssl_email="",
        ubuntu_version="22.04",
        dry_run=False,
        debug=False,
        enable_passwordless_restart=True,
    )
    defaults.update(overrides)
    return InstallContext(**defaults)


# ── utils/sudoers.py ──────────────────────────────────────────────────────────


class TestSudoersUtil:
    def test_is_managed_false_when_file_missing(self, tmp_path):
        with patch("frappe_cli.utils.sudoers.SUDOERS_PATH", tmp_path / "nofile"):
            from frappe_cli.utils.sudoers import is_managed

            assert is_managed() is False

    def test_is_managed_true_when_marker_present(self, tmp_path):
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("# Managed by frappe-cli\nsome rule\n")
        with patch("frappe_cli.utils.sudoers.SUDOERS_PATH", drop_in):
            from frappe_cli.utils.sudoers import is_managed

            assert is_managed() is True

    def test_is_managed_false_when_no_marker(self, tmp_path):
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("custom rule without marker\n")
        with patch("frappe_cli.utils.sudoers.SUDOERS_PATH", drop_in):
            from frappe_cli.utils.sudoers import is_managed

            assert is_managed() is False

    def test_path_exists_falls_back_to_sudo_test_on_permission_error(self, tmp_path):
        """Regression: /etc/sudoers.d/ is mode 0750, so Path.exists() raises."""
        fake_path = tmp_path / "frappe-cli"
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", fake_path),
            patch.object(
                type(fake_path), "exists", side_effect=PermissionError(13, "denied")
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            from frappe_cli.utils.sudoers import path_exists

            assert path_exists("secret") is True
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[:3] == ["sudo", "-S", "test"]

    def test_path_exists_returns_false_without_password_when_stat_denied(
        self, tmp_path
    ):
        fake_path = tmp_path / "frappe-cli"
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", fake_path),
            patch.object(
                type(fake_path), "exists", side_effect=PermissionError(13, "denied")
            ),
        ):
            from frappe_cli.utils.sudoers import path_exists

            assert path_exists() is False

    def test_is_managed_reads_root_owned_file_via_sudo(self, tmp_path):
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("# Managed by frappe-cli\nrule\n")
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", drop_in),
            patch.object(
                type(drop_in), "read_text", side_effect=PermissionError(13, "denied")
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [],
                0,
                stdout=b"# Managed by frappe-cli\nrule\n",
                stderr=b"",
            )
            from frappe_cli.utils.sudoers import is_managed

            assert is_managed("secret") is True
        mock_run.assert_called_once()

    def test_enable_calls_visudo_and_install(self, tmp_path):
        fake_path = tmp_path / "frappe-cli"
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", fake_path),
            patch("frappe_cli.utils.sudoers._sudo_run") as mock_sudo,
            patch("subprocess.run") as mock_run,
            patch("getpass.getuser", return_value="testuser"),
        ):
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            from frappe_cli.utils.sudoers import enable

            enable("secret")

        # visudo -c was called
        visudo_called = any("visudo" in str(call) for call in mock_run.call_args_list)
        assert visudo_called
        # install was called via _sudo_run
        assert mock_sudo.called

    def test_enable_dry_run_makes_no_system_calls(self, tmp_path):
        fake_path = tmp_path / "frappe-cli"
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", fake_path),
            patch("frappe_cli.utils.sudoers._sudo_run") as mock_sudo,
            patch("subprocess.run") as mock_run,
        ):
            from frappe_cli.utils.sudoers import enable

            enable("secret", dry_run=True)
        mock_sudo.assert_not_called()
        mock_run.assert_not_called()

    def test_enable_refuses_unmanaged_existing_file(self, tmp_path):
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("custom rule\n")
        with patch("frappe_cli.utils.sudoers.SUDOERS_PATH", drop_in):
            from frappe_cli.utils.sudoers import enable

            with pytest.raises(RuntimeError, match="not created by frappe-cli"):
                enable("secret")

    def test_disable_removes_managed_file(self, tmp_path):
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("# Managed by frappe-cli\nrule\n")
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", drop_in),
            patch("frappe_cli.utils.sudoers._sudo_run") as mock_sudo,
        ):
            from frappe_cli.utils.sudoers import disable

            disable("secret")
        mock_sudo.assert_called_once()
        assert "rm" in mock_sudo.call_args[0][0]

    def test_disable_noop_when_file_missing(self, tmp_path):
        fake_path = tmp_path / "frappe-cli"
        with (
            patch("frappe_cli.utils.sudoers.SUDOERS_PATH", fake_path),
            patch("frappe_cli.utils.sudoers._sudo_run") as mock_sudo,
        ):
            from frappe_cli.utils.sudoers import disable

            disable("secret")
        mock_sudo.assert_not_called()

    def test_disable_refuses_unmanaged_file(self, tmp_path):
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("custom rule\n")
        with patch("frappe_cli.utils.sudoers.SUDOERS_PATH", drop_in):
            from frappe_cli.utils.sudoers import disable

            with pytest.raises(RuntimeError, match="not created by frappe-cli"):
                disable("secret")


# ── SudoersSetupStep ──────────────────────────────────────────────────────────


class TestSudoersSetupStep:
    def test_check_skipped_when_opted_out(self):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx(enable_passwordless_restart=False)
        assert step.check(ctx) is True  # True = can skip

    def test_check_false_when_opted_in_and_not_yet_configured(self, tmp_path):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx(enable_passwordless_restart=True)
        fake_path = tmp_path / "frappe-cli"
        with patch("frappe_cli.install.steps.sudoers.is_managed", return_value=False):
            assert step.check(ctx) is False

    def test_check_true_when_already_configured(self):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx(enable_passwordless_restart=True)
        with patch("frappe_cli.install.steps.sudoers.is_managed", return_value=True):
            assert step.check(ctx) is True

    def test_run_calls_enable_when_opted_in(self):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx(enable_passwordless_restart=True)
        with patch("frappe_cli.install.steps.sudoers.enable") as mock_enable:
            step.run(ctx)
        mock_enable.assert_called_once_with("secret", dry_run=False)

    def test_run_skips_when_opted_out(self):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx(enable_passwordless_restart=False)
        with patch("frappe_cli.install.steps.sudoers.enable") as mock_enable:
            step.run(ctx)
        mock_enable.assert_not_called()

    def test_run_dry_run_mode(self):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx(enable_passwordless_restart=True, dry_run=True)
        with patch("frappe_cli.install.steps.sudoers.enable") as mock_enable:
            step.run(ctx)
        mock_enable.assert_not_called()

    def test_rollback_calls_disable_when_managed(self, tmp_path):
        from frappe_cli.install.steps.sudoers import SudoersSetupStep

        step = SudoersSetupStep()
        ctx = make_ctx()
        drop_in = tmp_path / "frappe-cli"
        drop_in.write_text("# Managed by frappe-cli\nrule\n")
        with (
            patch("frappe_cli.install.steps.sudoers.SUDOERS_PATH", drop_in),
            patch("frappe_cli.install.steps.sudoers.path_exists", return_value=True),
            patch("frappe_cli.install.steps.sudoers.is_managed", return_value=True),
            patch("frappe_cli.utils.sudoers.disable") as mock_disable,
        ):
            step.rollback(ctx)
        mock_disable.assert_called_once()


# ── fp sudo commands ──────────────────────────────────────────────────────────


class TestFpSudoCommands:
    def test_status_enabled(self):
        runner = CliRunner()
        with (
            patch("frappe_cli.dev.sudo_commands.is_enabled", return_value=True),
            patch("frappe_cli.dev.sudo_commands.is_managed", return_value=True),
            patch("frappe_cli.dev.sudo_commands.SUDOERS_PATH") as mock_path,
        ):
            mock_path.exists.return_value = True
            result = runner.invoke(cli, ["sudo", "status"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    def test_status_disabled(self):
        runner = CliRunner()
        with patch("frappe_cli.dev.sudo_commands.is_enabled", return_value=False):
            result = runner.invoke(cli, ["sudo", "status"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        assert "enable-restart" in result.output

    def test_enable_restart_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sudo", "enable-restart", "--dry-run"])
        assert result.exit_code == 0
        assert "would write" in result.output.lower()

    def test_enable_restart_already_managed(self):
        runner = CliRunner()
        with (
            patch(
                "frappe_cli.dev.sudo_commands.Prompt.ask",
                return_value="secret",
            ),
            patch("frappe_cli.dev.sudo_commands.is_managed", return_value=True),
        ):
            result = runner.invoke(cli, ["sudo", "enable-restart"])
        assert result.exit_code == 0
        assert "already enabled" in result.output.lower()

    def test_disable_restart_dry_run(self, tmp_path):
        fake_path = tmp_path / "frappe-cli"
        fake_path.write_text("# Managed by frappe-cli\nrule\n")
        runner = CliRunner()
        with patch("frappe_cli.dev.sudo_commands.SUDOERS_PATH", fake_path):
            result = runner.invoke(cli, ["sudo", "disable-restart", "--dry-run"])
        assert result.exit_code == 0
        assert "would remove" in result.output.lower()

    def test_disable_restart_no_file(self, tmp_path):
        fake_path = tmp_path / "frappe-cli"
        runner = CliRunner()
        with (
            patch("frappe_cli.dev.sudo_commands.SUDOERS_PATH", fake_path),
            patch(
                "frappe_cli.dev.sudo_commands.Prompt.ask",
                return_value="secret",
            ),
            patch(
                "frappe_cli.dev.sudo_commands.path_exists",
                return_value=False,
            ),
        ):
            result = runner.invoke(cli, ["sudo", "disable-restart"])
        assert result.exit_code == 0
        assert "nothing to remove" in result.output.lower()
