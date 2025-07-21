
from click.testing import CliRunner
import frappe_cli.cli as cli


def test_service_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['service', '--help'])
    assert result.exit_code == 0
    assert 'Service management commands' in result.output


def test_service_restart_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['service', 'restart', '--help'])
    assert result.exit_code == 0
    assert ('Restart Frappe services' in result.output or
            'Restart services' in result.output)
