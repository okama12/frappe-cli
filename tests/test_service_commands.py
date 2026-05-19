import importlib
from unittest.mock import patch

from click.testing import CliRunner

import frappe_cli.cli as cli

# `service/__init__.py` does `from .status import status` (the Click command),
# which shadows the submodule on `frappe_cli.service.status`. Always resolve the
# real module via importlib for patching.
_STATUS_MOD = importlib.import_module("frappe_cli.service.status")


def test_service_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["service", "--help"])
    assert result.exit_code == 0
    assert "Service management commands" in result.output


def test_service_restart_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["service", "restart", "--help"])
    assert result.exit_code == 0
    assert (
        "Restart Frappe services" in result.output
        or "Restart services" in result.output
    )


def test_service_status_lists_apps_with_bench_cwd(tmp_path, monkeypatch):
    """list-apps must run with cwd set to the bench directory."""
    bench = tmp_path / "my-bench"
    site_dir = bench / "sites" / "erp.example.com"
    site_dir.mkdir(parents=True)
    (site_dir / "site_config.json").write_text("{}")

    list_apps_calls: list[dict] = []

    def fake_runner_run(cmd, description=None, check=True, cwd=None):
        if cmd == ["bench", "--site", "erp.example.com", "list-apps"]:
            list_apps_calls.append({"cmd": cmd, "cwd": cwd})
            return "frappe  15.0 version-15\nerpnext 15.0 version-15"
        if cmd == ["which", "bench"]:
            return "/home/user/.local/bin/bench"
        if cmd == ["bench", "--version"]:
            return "5.29.1"
        if cmd[:2] == ["systemctl", "is-active"]:
            return "active"
        if cmd[:2] == ["cat", "/etc/os-release"]:
            return 'PRETTY_NAME="Ubuntu 24.04"\n'
        if cmd == ["free", "-h"]:
            return "Mem: 7.8Gi 1.5Gi 6.3Gi\n"
        if cmd == ["df", "-h", "/"]:
            return "Filesystem Size Used Avail Use% Mounted on\n/dev/sda1 145G 49G 96G 34% /\n"
        return ""

    def fake_isdir(path):
        return str(path) in {str(bench), str(site_dir), str(bench / "sites")}

    monkeypatch.chdir(tmp_path)
    with (
        patch.object(_STATUS_MOD.shell_runner, "run", side_effect=fake_runner_run),
        patch.object(_STATUS_MOD.os.path, "isdir", side_effect=fake_isdir),
        patch.object(_STATUS_MOD, "cert_exists", return_value=False),
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli.cli,
            [
                "service",
                "status",
                "--bench-name",
                str(bench),
                "--site-name",
                "erp.example.com",
            ],
        )

    assert result.exit_code == 0, result.output
    assert len(list_apps_calls) == 1
    assert list_apps_calls[0]["cwd"] == str(bench)
    assert "Installed apps:" in result.output
    assert "erpnext" in result.output
