"""Short commands are public commands with shared execution and target rules."""

import json
import subprocess
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from frappe_cli.cli import cli


@pytest.fixture
def bench(tmp_path, monkeypatch):
    root = tmp_path / "custom-location" / "demo-bench"
    (root / "apps").mkdir(parents=True)
    for name in ("alpha.local", "beta.local"):
        site = root / "sites" / name
        site.mkdir(parents=True)
        (site / "site_config.json").write_text(json.dumps({}))
    (root / ".fp.yaml").write_text("site: alpha.local\n")
    monkeypatch.chdir(root)
    return root


@pytest.mark.parametrize(
    "command",
    [
        "r",
        "m",
        "c",
        "db",
        "get",
        "add",
        "apps",
        "backup",
        "setup",
        "new",
        "prod",
        "reload",
        "deps",
        "node",
        "database",
        "ssl",
    ],
)
def test_primary_commands_are_registered(command):
    assert command in cli.commands
    result = CliRunner().invoke(cli, [command, "--help"])
    assert result.exit_code == 0, result.output


def test_prod_uses_current_actual_bench_path(bench):
    with patch("frappe_cli.actions.run_step") as run, patch(
        "getpass.getpass", return_value="secret"
    ):
        result = CliRunner().invoke(cli, ["prod"])
    assert result.exit_code == 0, result.output
    step, context = run.call_args.args
    assert step.name == "production_setup"
    assert context.bench_path == bench


def test_reload_keeps_distinct_operation_from_restart(bench):
    with patch("frappe_cli.actions.run_step") as run:
        result = CliRunner().invoke(cli, ["reload", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert run.call_args.args[0].name == "bench_restart"
    assert run.call_args.args[1].app_url


def test_site_override_has_correct_position_and_does_not_change_selection(bench):
    original = (bench / ".fp.yaml").read_bytes()
    with patch(
        "frappe_cli.dev.commands.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0),
    ) as run:
        result = CliRunner().invoke(cli, ["m", "-s", "beta.local", "--skip-failing"])
    assert result.exit_code == 0, result.output
    assert run.call_args.args[0] == [
        "bench",
        "--site",
        "beta.local",
        "migrate",
        "--skip-failing",
    ]
    assert (bench / ".fp.yaml").read_bytes() == original


def test_stale_saved_site_is_rejected_before_execution(bench):
    (bench / ".fp.yaml").write_text("site: missing.local\n")
    with patch("frappe_cli.dev.commands.subprocess.run") as run:
        result = CliRunner().invoke(cli, ["m"])
    assert result.exit_code != 0
    run.assert_not_called()
    assert "no longer exists" in result.output


def test_bench_command_rejects_site_override(bench):
    with patch("frappe_cli.dev.commands.subprocess.run") as run:
        result = CliRunner().invoke(cli, ["r", "-s", "alpha.local"])
    assert result.exit_code == 2
    run.assert_not_called()


def test_backup_uses_context_and_forwards_files_option(bench):
    with patch(
        "frappe_cli.dev.commands.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0),
    ) as run:
        result = CliRunner().invoke(cli, ["backup", "--with-files"])
    assert result.exit_code == 0, result.output
    assert run.call_args.args[0] == [
        "bench",
        "--site",
        "alpha.local",
        "backup",
        "--with-files",
    ]


def test_get_preview_performs_no_remote_branch_detection(bench):
    with patch("frappe_cli.actions.resolve_app_branch") as resolve, patch(
        "frappe_cli.actions.run_step"
    ) as run:
        result = CliRunner().invoke(
            cli, ["get", "https://github.com/example/app", "--dry-run"]
        )
    assert result.exit_code == 0, result.output
    resolve.assert_not_called()
    assert run.call_args.args[1].bench_path == bench


def test_init_supports_explicit_parent_without_creating_it(tmp_path):
    with patch("frappe_cli.actions.run_step") as run:
        result = CliRunner().invoke(
            cli, ["init", "new-bench", "--path", str(tmp_path), "--dry-run"]
        )
    assert result.exit_code == 0, result.output
    assert run.call_args.args[1].bench_path == tmp_path / "new-bench"
    assert not (tmp_path / "new-bench").exists()


def test_passthrough_preview_executes_nothing(bench):
    with patch("frappe_cli.dev.commands.subprocess.run") as run:
        result = CliRunner().invoke(cli, ["m", "--dry-run"])
    assert result.exit_code == 0
    assert "bench --site alpha.local migrate" in result.output
    run.assert_not_called()


def test_get_uses_frappe_branch_from_existing_bench(bench):
    metadata = bench / "apps" / "frappe" / ".git"
    metadata.mkdir(parents=True)
    (metadata / "HEAD").write_text("ref: refs/heads/version-16\n")
    with patch(
        "frappe_cli.actions.resolve_app_branch", return_value=("version-16", None)
    ) as resolve, patch("frappe_cli.actions.run_step") as run:
        result = CliRunner().invoke(cli, ["get", "erpnext"])
    assert result.exit_code == 0, result.output
    resolve.assert_called_once_with("erpnext", frappe_branch="version-16")
    assert run.call_args.args[1].app_branch == "version-16"
