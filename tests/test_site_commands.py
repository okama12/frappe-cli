from click.testing import CliRunner

import frappe_cli.cli as cli


def test_site_create_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "create", "--help"])
    assert result.exit_code == 0
    assert "Create a new Frappe site" in result.output


def test_site_delete_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "delete", "--help"])
    assert result.exit_code == 0
    assert "Delete a Frappe site" in result.output or "Delete site" in result.output


def test_site_list_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "list", "--help"])
    assert result.exit_code == 0
    assert "List all Frappe sites" in result.output or "List sites" in result.output


def test_site_backup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "backup", "--help"])
    assert result.exit_code == 0
    assert "Run bench backup for a site" in result.output


def test_site_restore_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "restore", "--help"])
    assert result.exit_code == 0
    assert "Restore a site from backup" in result.output
