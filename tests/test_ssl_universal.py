"""General HTTPS setup must not require a Frappe site or touch real services."""

import importlib
import socket
import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from frappe_cli.cli import cli
from frappe_cli.ssl.secure import Runner, certificate_valid, configure_https

secure_module = importlib.import_module("frappe_cli.ssl.secure")


def result(stdout=b"", code=0, stderr=b""):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


def configured_runner():
    runner = MagicMock()

    def run(command, **kwargs):
        if command == ["nginx", "-T"]:
            return result(b"server {\n server_name api.example.com;\n}\n")
        if command[0] == "dpkg-query":
            return result(b"install ok installed")
        return result()

    runner.run.side_effect = run
    return runner


def test_direct_ssl_domain_reaches_general_operation():
    with patch.object(secure_module, "configure_https") as configure:
        invocation = CliRunner().invoke(
            cli, ["ssl", "api.example.com", "--email", "owner@example.com"]
        )
    assert invocation.exit_code == 0, invocation.output
    assert configure.call_args.args == ("api.example.com",)
    assert configure.call_args.kwargs["email"] == "owner@example.com"


def test_ssl_help_exposes_domain_and_direct_options():
    invocation = CliRunner().invoke(cli, ["ssl", "--help"])
    assert invocation.exit_code == 0
    assert "[DOMAIN]" in invocation.output
    assert "--method" in invocation.output
    assert "--dry-run" in invocation.output
    assert "list" in invocation.output
    invocation = CliRunner().invoke(cli, ["ssl", "api.example.com", "--help"])
    assert "ssl secure" not in invocation.output


def test_legacy_ssl_setup_falls_back_when_no_bench_exists():
    legacy = importlib.import_module("frappe_cli.ssl.setup")
    with patch.object(
        legacy, "_find_bench_for_site", side_effect=click.ClickException("No bench")
    ), patch.object(secure_module, "configure_https") as configure:
        invocation = CliRunner().invoke(
            cli, ["ssl", "setup", "--site-name", "api.example.com"]
        )
    assert invocation.exit_code == 0, invocation.output
    assert configure.call_args.args == ("api.example.com",)


def test_general_nginx_ssl_never_invokes_bench():
    runner = configured_runner()
    with patch.object(
        secure_module,
        "_find_bench_for_site",
        side_effect=click.ClickException("No bench"),
    ), patch.object(secure_module.socket, "getaddrinfo", return_value=[]), patch.object(
        secure_module, "Runner", return_value=runner
    ), patch.object(
        secure_module.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"
    ), patch.object(
        secure_module, "certificate_valid", side_effect=[False, True]
    ), patch.object(
        secure_module, "verify_https"
    ) as verify:
        configure_https(
            "api.example.com", email="owner@example.com", sudo_password="secret"
        )
    commands = [call.args[0] for call in runner.run.call_args_list]
    certbot = next(command for command in commands if "--cert-name" in command)
    assert "--nginx" in certbot
    assert "--redirect" in certbot
    assert not any("bench" in command for command in commands)
    assert ["systemctl", "enable", "--now", "certbot.timer"] in commands
    verify.assert_called_once_with("api.example.com")


def test_unknown_domain_is_not_attached_to_an_arbitrary_nginx_site():
    runner = configured_runner()
    with patch.object(
        secure_module,
        "_find_bench_for_site",
        side_effect=click.ClickException("No bench"),
    ), patch.object(secure_module.socket, "getaddrinfo", return_value=[]), patch.object(
        secure_module, "Runner", return_value=runner
    ), patch.object(
        secure_module.shutil,
        "which",
        side_effect=lambda name: "/usr/bin/nginx" if name == "nginx" else None,
    ), patch.object(
        secure_module, "certificate_valid", return_value=False
    ), patch(
        "frappe_cli.ui.terminal.interactive", return_value=False
    ):
        with pytest.raises(
            click.ClickException, match="No supported website configuration"
        ):
            configure_https(
                "other.example.com", email="owner@example.com", sudo_password="secret"
            )
    assert not any(call.args[0][0] == "certbot" for call in runner.run.call_args_list)


def test_preview_has_no_dns_privilege_or_certificate_commands():
    with patch.object(secure_module.socket, "getaddrinfo") as dns, patch.object(
        secure_module, "Runner"
    ) as runner, patch("frappe_cli.ui.terminal.ask") as ask:
        invocation = CliRunner().invoke(cli, ["ssl", "api.example.com", "--dry-run"])
    assert invocation.exit_code == 0, invocation.output
    dns.assert_not_called()
    runner.assert_not_called()
    ask.assert_not_called()
    assert "No commands ran" in invocation.output


def test_dns_failure_happens_before_privilege_prompt():
    with patch.object(
        secure_module,
        "_find_bench_for_site",
        side_effect=click.ClickException("No bench"),
    ), patch.object(
        secure_module.socket, "getaddrinfo", side_effect=socket.gaierror("not found")
    ), patch(
        "frappe_cli.ui.terminal.ask"
    ) as ask, patch.object(
        secure_module, "Runner"
    ) as runner:
        with pytest.raises(click.ClickException, match="DNS lookup failed"):
            configure_https("api.example.com")
    ask.assert_not_called()
    runner.assert_not_called()


def test_webroot_mode_reports_certificate_only_not_live_https(tmp_path):
    runner = configured_runner()
    with patch("frappe_cli.ui.terminal.ask", return_value="secret"), patch.object(
        secure_module.socket, "getaddrinfo", return_value=[]
    ), patch.object(secure_module, "Runner", return_value=runner), patch.object(
        secure_module.shutil, "which", return_value="/usr/bin/tool"
    ), patch.object(
        secure_module, "certificate_valid", side_effect=[False, True]
    ), patch.object(
        secure_module, "verify_https"
    ) as verify:
        invocation = CliRunner().invoke(
            cli,
            [
                "ssl",
                "api.example.com",
                "--method",
                "webroot",
                "--webroot",
                str(tmp_path),
                "--email",
                "owner@example.com",
            ],
        )
    assert invocation.exit_code == 0, invocation.output
    verify.assert_not_called()
    assert "Certificate ready" in invocation.output
    assert "HTTPS verified" not in invocation.output
    commands = [call.args[0] for call in runner.run.call_args_list]
    certificate_command = next(
        command for command in commands if "--cert-name" in command
    )
    assert "certonly" in certificate_command
    assert "--webroot" in certificate_command
    assert str(tmp_path) in certificate_command


def test_certificate_file_alone_is_not_treated_as_healthy():
    runner = MagicMock()
    runner.run.return_value = result(
        b"Hostname api.example.com does NOT match certificate"
    )
    assert not certificate_valid("api.example.com", runner)
    runner.run.return_value = result(b"Hostname api.example.com does match certificate")
    assert certificate_valid("api.example.com", runner)


def test_failed_endpoint_verification_is_not_reported_as_success():
    runner = configured_runner()
    with patch("frappe_cli.ui.terminal.ask", return_value="secret"), patch.object(
        secure_module.socket, "getaddrinfo", return_value=[]
    ), patch.object(secure_module, "Runner", return_value=runner), patch.object(
        secure_module.shutil, "which", return_value="/usr/bin/tool"
    ), patch.object(
        secure_module, "certificate_valid", side_effect=[False, True]
    ), patch.object(
        secure_module,
        "verify_https",
        side_effect=click.ClickException("HTTPS verification failed"),
    ):
        invocation = CliRunner().invoke(
            cli,
            [
                "ssl",
                "api.example.com",
                "--method",
                "nginx",
                "--email",
                "owner@example.com",
            ],
        )
    assert invocation.exit_code == 1
    assert "HTTPS verified:" not in invocation.output
    assert "verification failed" in invocation.output


def test_runner_keeps_password_off_argv_and_redacts_failures():
    with patch.object(secure_module.os, "geteuid", return_value=1000), patch.object(
        secure_module.subprocess,
        "run",
        side_effect=[result(), result(stderr=b"Failure with secret-password", code=1)],
    ) as command:
        with pytest.raises(click.ClickException) as failure:
            Runner("secret-password").run(["nginx", "-t"])
    assert "secret-password" not in str(failure.value)
    assert all("secret-password" not in part for part in command.call_args.args[0])
    assert b"secret-password" in command.call_args_list[0].kwargs["input"]
    assert command.call_args.kwargs["input"] == b""


@pytest.mark.parametrize(
    "domain", ["localhost", "dev.local", "../example.com", "-bad.example.com"]
)
def test_invalid_domains_fail_before_commands(domain):
    with patch.object(secure_module, "Runner") as runner:
        with pytest.raises(click.BadParameter):
            configure_https(domain, dry_run=True)
    runner.assert_not_called()


def test_proxy_creation_only_writes_a_new_managed_file():
    runner = MagicMock()
    configs = []

    def run(command, **kwargs):
        if command[:2] == ["test", "-e"]:
            return result(code=1)
        if command[0] == "install":
            configs.append(secure_module.Path(command[-2]).read_text())
        return result()

    runner.run.side_effect = run
    with patch.object(secure_module.shutil, "which", return_value="/usr/bin/tool"):
        path = secure_module._proxy("api.example.com", 8000, runner)
    assert path.startswith("/etc/nginx/conf.d/fp-")
    assert len(configs) == 1
    assert "server_name api.example.com;" in configs[0]
    assert "proxy_pass http://127.0.0.1:8000;" in configs[0]
    assert ["systemctl", "reload", "nginx"] in [
        call.args[0] for call in runner.run.call_args_list
    ]


def test_proxy_does_not_overwrite_existing_file():
    runner = MagicMock()
    runner.run.return_value = result()
    with patch.object(secure_module.shutil, "which", return_value="/usr/bin/tool"):
        with pytest.raises(click.ClickException, match="already exists"):
            secure_module._proxy("api.example.com", 8000, runner)
    assert not any(call.args[0][0] == "install" for call in runner.run.call_args_list)


def test_proxy_restores_previous_configuration_on_failed_validation():
    runner = MagicMock()
    copied = []

    def run(command, **kwargs):
        if command[:2] == ["test", "-e"]:
            return result(code=1)
        if command[0] == "install":
            copied.append(command[-1])
        if command == ["nginx", "-t"] and copied:
            raise click.ClickException("Invalid config")
        return result()

    runner.run.side_effect = run
    with patch.object(secure_module.shutil, "which", return_value="/usr/bin/tool"):
        with pytest.raises(click.ClickException, match="Invalid config"):
            secure_module._proxy("api.example.com", 8000, runner)
    commands = [call.args[0] for call in runner.run.call_args_list]
    assert ["rm", "--", copied[0]] in commands


def test_ssl_proxy_preview_requires_no_host_operations():
    with patch.object(secure_module, "Runner") as runner:
        invocation = CliRunner().invoke(
            cli, ["ssl", "api.example.com", "--port", "8000", "--dry-run"]
        )
    assert invocation.exit_code == 0, invocation.output
    assert "127.0.0.1:8000" in invocation.output
    runner.assert_not_called()


def test_frappe_integration_reuses_account_and_keeps_bench_configuration(tmp_path):
    site = tmp_path / "sites" / "api.example.com"
    site.mkdir(parents=True)
    (site / "site_config.json").write_text("{}")
    runner = configured_runner()
    with patch.object(
        secure_module.socket, "getaddrinfo", return_value=[]
    ), patch.object(secure_module, "Runner", return_value=runner), patch.object(
        secure_module.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"
    ), patch.object(
        secure_module, "certificate_valid", side_effect=[False, True]
    ), patch.object(
        secure_module, "verify_https"
    ):
        configure_https(
            "api.example.com",
            bench=tmp_path,
            email="owner@example.com",
            sudo_password="secret",
        )
    commands = [call.args[0] for call in runner.run.call_args_list]
    assert any(
        "lets-encrypt" in command and "/usr/bin/bench" in command
        for command in commands
    )
    assert ["certbot", "show_account"] in commands
    assert not any("register" in command for command in commands)
    assert not any("--nginx" in command for command in commands)
