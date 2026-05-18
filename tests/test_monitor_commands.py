import frappe_cli.cli as cli
from click.testing import CliRunner


def test_monitor_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["monitor", "--help"])
    assert result.exit_code == 0
    assert "Monitoring commands" in result.output or "Monitor" in result.output


def test_monitor_logs_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["monitor", "logs", "--help"])
    assert result.exit_code == 0
    assert "Show live logs for a service" in result.output
