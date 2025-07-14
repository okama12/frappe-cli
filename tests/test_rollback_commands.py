import pytest
from click.testing import CliRunner
import frappe_cli.cli as cli

def test_rollback_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['rollback', '--help'])
    assert result.exit_code == 0
    assert 'Rollback/uninstall commands' in result.output or 'Rollback' in result.output

def test_rollback_uninstall_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['rollback', 'uninstall', '--help'])
    assert result.exit_code == 0
    assert 'Uninstall Frappe' in result.output or 'Uninstall' in result.output
