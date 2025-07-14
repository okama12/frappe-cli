import pytest
from click.testing import CliRunner
import frappe_cli.cli as cli

def test_backup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['backup', '--help'])
    assert result.exit_code == 0
    assert 'Backup management commands' in result.output

def test_backup_setup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['backup', 'setup', '--help'])
    assert result.exit_code == 0
    assert 'Setup automated backups' in result.output or 'Setup backup' in result.output
