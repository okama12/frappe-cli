
from click.testing import CliRunner
import frappe_cli.cli as cli


def test_app_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['app', '--help'])
    assert result.exit_code == 0
    assert 'App management commands' in result.output


def test_app_clone_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['app', 'clone', '--help'])
    assert result.exit_code == 0
    assert ('Clone a Frappe app' in result.output or
            'Clone app' in result.output)
