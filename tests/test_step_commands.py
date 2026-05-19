"""Tests for the `frappe step ...` group."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import frappe_cli.cli as cli
from frappe_cli.install.steps.base import StepError
from frappe_cli.step._runner import build_context, run_step
from frappe_cli.step.commands import ALL_STEP_COMMANDS

# ── discovery ────────────────────────────────────────────────────────────────


def test_step_group_help_lists_all_commands():
    """`frappe step --help` must enumerate every step command (kebab-case)."""
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["step", "--help"])
    assert result.exit_code == 0
    expected = [
        "system-update",
        "system-deps",
        "uv-check",
        "nodejs",
        "mariadb-install",
        "mariadb-secure",
        "redis",
        "wkhtmltopdf",
        "bench-install",
        "bench-init",
        "site-create",
        "app-get",
        "dns-multitenant",
        "production",
        "app-install",
        "bench-restart",
        "ssl",
        "list",
    ]
    for name in expected:
        assert name in result.output, f"Missing command {name} in `step --help`"


def test_step_list_includes_every_wizard_step():
    """`frappe step list` shows the same step count as wizard's ALL_STEPS."""
    from frappe_cli.install.steps import ALL_STEPS

    runner = CliRunner()
    result = runner.invoke(cli.cli, ["step", "list"])
    assert result.exit_code == 0
    for step_inst in ALL_STEPS:
        assert step_inst.description in result.output


def test_every_step_command_help_renders():
    """Each generated subcommand exposes its own --help without errors."""
    runner = CliRunner()
    for cmd in ALL_STEP_COMMANDS:
        result = runner.invoke(cli.cli, ["step", cmd.name, "--help"])
        assert (
            result.exit_code == 0
        ), f"`step {cmd.name} --help` failed: {result.output}"
        assert "--force" in result.output
        assert "--dry-run" in result.output


# ── runner short-circuit / error paths ───────────────────────────────────────


class TestRunStep:
    def test_short_circuits_when_check_returns_true(self):
        step = MagicMock(name="step")
        step.name = "fake"
        step.description = "Fake"
        step.check.return_value = True
        ctx = build_context(needs_sudo=False, sudo_password="")
        run_step(step, ctx)
        step.check.assert_called_once_with(ctx)
        step.run.assert_not_called()

    def test_force_skips_check_short_circuit(self):
        step = MagicMock(name="step")
        step.name = "fake"
        step.description = "Fake"
        step.check.return_value = True
        ctx = build_context(needs_sudo=False, sudo_password="")
        run_step(step, ctx, force=True)
        step.run.assert_called_once_with(ctx)

    def test_runs_when_check_returns_false(self):
        step = MagicMock(name="step")
        step.name = "fake"
        step.description = "Fake"
        step.check.return_value = False
        ctx = build_context(needs_sudo=False, sudo_password="")
        run_step(step, ctx)
        step.run.assert_called_once_with(ctx)

    def test_check_exception_treated_as_not_done(self):
        """If check() crashes we should still attempt run(), not abort."""
        step = MagicMock(name="step")
        step.name = "fake"
        step.description = "Fake"
        step.check.side_effect = RuntimeError("oops")
        ctx = build_context(needs_sudo=False, sudo_password="")
        run_step(step, ctx)
        step.run.assert_called_once_with(ctx)

    def test_step_error_is_converted_to_click_exception(self):
        import click as _click

        step = MagicMock(name="step")
        step.name = "fake"
        step.description = "Fake"
        step.check.return_value = False
        step.run.side_effect = StepError("boom", hint="check redis")
        ctx = build_context(needs_sudo=False, sudo_password="")
        with pytest.raises(_click.ClickException) as exc:
            run_step(step, ctx)
        assert "boom" in exc.value.message
        assert "check redis" in exc.value.message


# ── build_context ────────────────────────────────────────────────────────────


class TestBuildContext:
    def test_no_sudo_prompt_when_needs_sudo_false(self):
        with patch("getpass.getpass") as gp:
            ctx = build_context(needs_sudo=False)
        gp.assert_not_called()
        assert ctx.sudo_password == ""

    def test_prompts_for_sudo_when_needed_and_not_provided(self):
        with patch("getpass.getpass", return_value="pw") as gp:
            ctx = build_context(needs_sudo=True)
        gp.assert_called_once()
        assert ctx.sudo_password == "pw"

    def test_skips_prompt_when_sudo_password_passed(self):
        with patch("getpass.getpass") as gp:
            ctx = build_context(needs_sudo=True, sudo_password="given")
        gp.assert_not_called()
        assert ctx.sudo_password == "given"

    def test_dry_run_skips_sudo_prompt(self):
        with patch("getpass.getpass") as gp:
            ctx = build_context(needs_sudo=True, dry_run=True)
        gp.assert_not_called()
        assert ctx.dry_run is True


# ── individual command wiring ────────────────────────────────────────────────


class TestStepCommandWiring:
    def test_dns_multitenant_invokes_step_run(self):
        """`step dns-multitenant` builds a ctx with bench_name and runs the step."""
        with patch("frappe_cli.step.commands.DnsMultitenantStep") as MockStep:
            instance = MockStep.return_value
            instance.name = "dns_multitenant"
            instance.description = "Enable DNS multitenant"
            instance.check.return_value = False
            runner = CliRunner()
            result = runner.invoke(
                cli.cli,
                ["step", "dns-multitenant", "--bench-name", "test5-bench"],
            )
        assert result.exit_code == 0, result.output
        instance.run.assert_called_once()
        ctx_arg = instance.run.call_args.args[0]
        assert ctx_arg.bench_name == "test5-bench"

    def test_ssl_command_passes_site_and_email(self):
        with (
            patch("frappe_cli.step.commands.SSLSetupStep") as MockStep,
            patch("getpass.getpass", return_value="pw"),
        ):
            instance = MockStep.return_value
            instance.name = "ssl_setup"
            instance.description = "Configure SSL (Let's Encrypt)"
            instance.check.return_value = False
            runner = CliRunner()
            result = runner.invoke(
                cli.cli,
                [
                    "step",
                    "ssl",
                    "--bench-name",
                    "test5-bench",
                    "--site-name",
                    "test5.example.com",
                    "--ssl-email",
                    "me@example.com",
                ],
            )
        assert result.exit_code == 0, result.output
        ctx_arg = instance.run.call_args.args[0]
        assert ctx_arg.bench_name == "test5-bench"
        assert ctx_arg.site_name == "test5.example.com"
        assert ctx_arg.ssl_email == "me@example.com"
        assert ctx_arg.sudo_password == "pw"

    def test_production_command_requires_bench_name(self):
        """Missing required option fails fast with a non-zero exit."""
        runner = CliRunner()
        result = runner.invoke(
            cli.cli, ["step", "production"], input="\n", catch_exceptions=False
        )
        # Click prompts for it since required; empty input -> abort or error
        assert result.exit_code != 0

    def test_step_error_surfaces_as_failure(self):
        with patch("frappe_cli.step.commands.RedisStep") as MockStep:
            instance = MockStep.return_value
            instance.name = "redis"
            instance.description = "Install Redis"
            instance.check.return_value = False
            instance.run.side_effect = StepError("redis fail", hint="check apt")
            runner = CliRunner()
            with patch("getpass.getpass", return_value="pw"):
                result = runner.invoke(cli.cli, ["step", "redis"])
        assert result.exit_code != 0
        assert "redis fail" in result.output
        assert "check apt" in result.output

    def test_force_flag_runs_even_when_check_true(self):
        with patch("frappe_cli.step.commands.DnsMultitenantStep") as MockStep:
            instance = MockStep.return_value
            instance.name = "dns_multitenant"
            instance.description = "Enable DNS multitenant"
            instance.check.return_value = True
            runner = CliRunner()
            result = runner.invoke(
                cli.cli,
                [
                    "step",
                    "dns-multitenant",
                    "--bench-name",
                    "test5-bench",
                    "--force",
                ],
            )
        assert result.exit_code == 0, result.output
        instance.run.assert_called_once()
