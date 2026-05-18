import frappe_cli.cli as cli
from click.testing import CliRunner


def test_ssl_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["ssl", "--help"])
    assert result.exit_code == 0
    assert "SSL/HTTPS management commands" in result.output or "SSL" in result.output


def test_ssl_setup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["ssl", "setup", "--help"])
    assert result.exit_code == 0
    assert "Set up SSL/HTTPS with Let's Encrypt" in result.output
