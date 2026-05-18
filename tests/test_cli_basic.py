import frappe_cli.cli as cli
from click.testing import CliRunner


def test_frappe_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["--help"])
    assert result.exit_code == 0
    assert "Frappe Installer CLI" in result.output
    assert "Commands:" in result.output


def test_site_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "--help"])
    assert result.exit_code == 0
    assert "Site management commands" in result.output


def test_missing_command():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["site", "create"])
    # Should fail due to missing required options
    assert result.exit_code != 0
    assert "Bench directory" in result.output or "not found" in result.output
