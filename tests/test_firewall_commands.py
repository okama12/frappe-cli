
from click.testing import CliRunner
import frappe_cli.cli as cli


def test_firewall_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['firewall', '--help'])
    assert result.exit_code == 0
    assert 'Firewall management commands' in result.output


def test_firewall_setup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ['firewall', 'setup', '--help'])
    assert result.exit_code == 0
    assert ('Setup firewall' in result.output or
            'Configure firewall' in result.output)
