import frappe_cli.cli as cli
from click.testing import CliRunner


def test_backup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["backup", "--help"])
    assert result.exit_code == 0
    assert "Backup management commands" in result.output


def test_backup_setup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["backup", "setup", "--help"])
    assert result.exit_code == 0
    assert "Set up robust backups with external HD and cron job" in result.output
