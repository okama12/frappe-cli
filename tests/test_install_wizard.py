# tests/test_install_wizard.py
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from frappe_cli.cli import cli


def test_install_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["install", "wizard", "--help"])
    assert result.exit_code == 0
    assert "--resume" in result.output


def test_install_dry_run_completes_all_steps():
    runner = CliRunner()
    from frappe_cli.install.context import InstallContext

    ctx = InstallContext(
        bench_name="frappe-bench",
        site_name="mysite.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15",
        sudo_password="s",
        mariadb_root_password="d",
        admin_password="a",
        ssl_email="e@e.com",
        ubuntu_version="22.04",
        dry_run=True,
    )
    step = MagicMock()
    step.name = "test_step"
    step.description = "Test step"
    step.check.return_value = False
    # Patch ALL_STEPS as a real list so it can be iterated twice
    # (once for renderer, once for the main loop)
    with patch("frappe_cli.install.wizard.collect_inputs", return_value=ctx), patch(
        "frappe_cli.install.wizard.ALL_STEPS", [step]
    ), patch("frappe_cli.install.wizard.save_state"), patch(
        "frappe_cli.install.wizard.clear_state"
    ):
        result = runner.invoke(cli, ["install", "wizard", "--dry-run"])
    assert result.exit_code == 0


def test_install_resume_fails_without_state():
    runner = CliRunner()
    with patch("frappe_cli.install.wizard.state_exists", return_value=False):
        result = runner.invoke(cli, ["install", "wizard", "--resume"])
    assert result.exit_code != 0


def test_skip_ssl_flag_omits_ssl_step():
    runner = CliRunner()
    from frappe_cli.install.context import InstallContext
    from frappe_cli.install.steps.ssl import SSLSetupStep

    ctx = InstallContext(
        bench_name="b",
        site_name="s.com",
        frappe_branch="v15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="v15",
        sudo_password="s",
        mariadb_root_password="d",
        admin_password="a",
        ssl_email="e@e.com",
        ubuntu_version="22.04",
        dry_run=False,
        skip_ssl=True,
    )
    ssl_step = MagicMock(spec=SSLSetupStep)
    ssl_step.name = "ssl_setup"
    ssl_step.description = "Configure SSL (Let's Encrypt)"
    with patch("frappe_cli.install.wizard.collect_inputs", return_value=ctx), patch(
        "frappe_cli.install.wizard.ALL_STEPS", [ssl_step]
    ), patch("frappe_cli.install.wizard.save_state"), patch(
        "frappe_cli.install.wizard.clear_state"
    ):
        result = runner.invoke(cli, ["install", "wizard", "--skip-ssl"])
    ssl_step.run.assert_not_called()
    assert result.exit_code == 0


def test_install_step_failure_exits_nonzero():
    runner = CliRunner()
    from frappe_cli.install.context import InstallContext
    from frappe_cli.install.steps.base import StepError

    ctx = InstallContext(
        bench_name="b",
        site_name="s.com",
        frappe_branch="v15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="v15",
        sudo_password="s",
        mariadb_root_password="d",
        admin_password="a",
        ssl_email="e@e.com",
        ubuntu_version="22.04",
        dry_run=False,
    )
    step = MagicMock()
    step.name = "failing_step"
    step.description = "Failing step"
    step.check.return_value = False
    step.run.side_effect = StepError("Something broke", hint="stderr output")
    with patch("frappe_cli.install.wizard.collect_inputs", return_value=ctx), patch(
        "frappe_cli.install.wizard.ALL_STEPS", [step]
    ), patch("frappe_cli.install.wizard.save_state"):
        result = runner.invoke(cli, ["install", "wizard"])
    assert result.exit_code != 0
