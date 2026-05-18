import frappe_cli.cli as cli
from click.testing import CliRunner


def test_firewall_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["firewall", "--help"])
    assert result.exit_code == 0
    assert "Firewall management commands" in result.output


def test_firewall_setup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["firewall", "setup", "--help"])
    assert result.exit_code == 0
    assert "Configure UFW firewall" in result.output
