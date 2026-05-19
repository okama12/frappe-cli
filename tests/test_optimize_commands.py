from click.testing import CliRunner

import frappe_cli.cli as cli


def test_optimize_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["optimize", "--help"])
    assert result.exit_code == 0
    assert "Performance tuning commands" in result.output or "Optimize" in result.output


def test_optimize_performance_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["optimize", "performance", "--help"])
    assert result.exit_code == 0
    assert "Optimize Frappe/Server performance" in result.output
