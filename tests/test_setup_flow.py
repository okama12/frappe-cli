"""Setup review, recovery, and previews must never touch the host."""

import io
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from rich.console import Console

from frappe_cli.cli import cli
from frappe_cli.install.context import InstallContext
from frappe_cli.install.plan import resolve_steps
from frappe_cli.install.state import InstallState, load_state, save_state
from frappe_cli.install.steps.base import StepError
from frappe_cli.install.steps.init_bench import BenchInitStep
from frappe_cli.ui.panels import print_plan
from frappe_cli.ui.prompts import collect_inputs
from frappe_cli.ui.steps import StepListRenderer


def context(tmp_path, **values):
    defaults = dict(
        bench_name="demo-bench",
        bench_parent=str(tmp_path),
        site_name="shop.example.com",
        frappe_branch="version-15",
        app_url="",
        app_branch="version-15",
        sudo_password="sudo-secret",
        mariadb_root_password="db-secret",
        admin_password="admin-secret",
        ssl_email="owner@example.com",
        ubuntu_version="24.04",
        dry_run=False,
    )
    defaults.update(values)
    return InstallContext(**defaults)


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr("frappe_cli.install.state.STATE_FILE", path)
    return path


def fake_step(name="system_deps"):
    step = MagicMock()
    step.name = name
    step.description = "Install dependencies"
    step.check.return_value = False
    return step


def test_setup_without_terminal_requires_task():
    with patch("frappe_cli.ui.terminal.interactive", return_value=False):
        result = CliRunner().invoke(cli, ["setup"])
    assert result.exit_code == 2
    assert "--task" in result.output


def test_setup_menu_dispatches_selected_task():
    with patch("frappe_cli.ui.terminal.interactive", return_value=True), patch(
        "frappe_cli.ui.terminal.choose", return_value="inspect"
    ) as choose, patch("frappe_cli.setup.shutil.which", return_value=None), patch(
        "frappe_cli.setup.discover_benches", return_value=[]
    ):
        result = CliRunner().invoke(cli, ["setup"])
    assert result.exit_code == 0, result.output
    choose.assert_called_once()
    assert "No benches discovered" in result.output


@pytest.mark.parametrize("interactive", [True, False])
def test_bare_fp_only_shows_help(interactive):
    runner = CliRunner()
    with patch("frappe_cli.ui.terminal.interactive", return_value=interactive), patch(
        "frappe_cli.ui.terminal.choose"
    ) as choose:
        result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert result.output == runner.invoke(cli, ["--help"]).output
    choose.assert_not_called()


def test_component_dependencies_have_canonical_order():
    resolved = resolve_steps(["app_install"])
    assert resolved.index("bench_init") < resolved.index("site_create")
    assert resolved.index("production_setup") < resolved.index("app_install")
    assert "mariadb_secure" in resolved
    assert "system_update" not in resolved
    assert "sudoers_setup" not in resolved
    with pytest.raises(click.BadParameter):
        resolve_steps(["unknown"])


def test_server_only_plan_asks_no_site_or_bench_questions():
    console = Console(file=io.StringIO())
    with patch("frappe_cli.ui.terminal.interactive", return_value=False), patch(
        "frappe_cli.ui.terminal.confirm", return_value=True
    ), patch("frappe_cli.ui.terminal.ask") as ask:
        ctx = collect_inputs(console, dry_run=True, components=["redis"])
    ask.assert_not_called()
    assert ctx.selected_steps == ["system_deps", "redis"]
    assert ctx.site_name == ""
    assert ctx.skip_ssl


def test_review_can_go_back_before_collecting_credentials(tmp_path):
    console = Console(file=io.StringIO())
    answers = {
        "Site domain": "shop.example.com",
        "Frappe branch": "version-15",
        "App name or repository (blank for Frappe only)": "",
        "Certificate email": "owner@example.com",
    }
    with patch(
        "frappe_cli.ui.prompts._bench_inputs",
        return_value=("demo-bench", str(tmp_path)),
    ) as bench, patch("frappe_cli.ui.terminal.interactive", return_value=True), patch(
        "frappe_cli.ui.terminal.ask", side_effect=lambda _, label, **kw: answers[label]
    ), patch(
        "frappe_cli.ui.terminal.confirm", return_value=False
    ), patch(
        "frappe_cli.ui.terminal.choose", side_effect=["edit", "continue"]
    ), patch(
        "frappe_cli.ui.prompts._credentials"
    ) as credentials:
        ctx = collect_inputs(console, dry_run=True)
    assert bench.call_count == 2
    credentials.assert_not_called()
    assert ctx.bench_path == tmp_path / "demo-bench"
    assert "sudoers_setup" not in ctx.selected_steps


def test_cancel_review_collects_no_credentials(tmp_path):
    with patch("frappe_cli.ui.terminal.interactive", return_value=True), patch(
        "frappe_cli.ui.terminal.choose", return_value="cancel"
    ), patch("frappe_cli.ui.prompts._credentials") as credentials:
        with pytest.raises(click.Abort):
            collect_inputs(Console(file=io.StringIO()), components=["redis"])
    credentials.assert_not_called()


def test_plan_never_displays_secrets(tmp_path):
    output = io.StringIO()
    ctx = context(tmp_path)
    print_plan(Console(file=output, width=44), ctx, [fake_step()])
    for value in (ctx.sudo_password, ctx.mariadb_root_password, ctx.admin_password):
        assert value not in output.getvalue()
    assert "Owner:" in output.getvalue()


def test_preview_does_not_execute_checks_or_touch_saved_progress(tmp_path, state_file):
    save_state(InstallState(bench_name="original"))
    original = state_file.read_bytes()
    step = fake_step()
    with patch(
        "frappe_cli.install.wizard.collect_inputs",
        return_value=context(tmp_path, dry_run=True),
    ), patch("frappe_cli.install.wizard.ALL_STEPS", [step]):
        result = CliRunner().invoke(cli, ["setup", "--task", "production", "--dry-run"])
    assert result.exit_code == 0, result.output
    step.check.assert_not_called()
    step.run.assert_not_called()
    assert state_file.read_bytes() == original
    assert "No installation commands ran" in result.output


def test_first_step_failure_has_resumable_state_and_preserves_files(
    tmp_path, state_file
):
    step = fake_step()
    step.run.side_effect = StepError(
        "Failed", hint="sudo-secret db-secret admin-secret"
    )
    with patch(
        "frappe_cli.install.wizard.collect_inputs", return_value=context(tmp_path)
    ), patch("frappe_cli.install.wizard.ALL_STEPS", [step]):
        result = CliRunner().invoke(cli, ["setup", "--task", "production"])
    assert result.exit_code == 1
    assert state_file.exists()
    assert load_state().completed_steps == []
    assert "fp setup --resume" in result.output
    step.rollback.assert_not_called()
    for secret in ("sudo-secret", "db-secret", "admin-secret"):
        assert secret not in result.output
        assert secret not in state_file.read_text()


def test_transient_retries_are_bounded(tmp_path, state_file):
    step = fake_step()
    step.run.side_effect = StepError("Temporary failure resolving package host")
    with patch(
        "frappe_cli.install.wizard.collect_inputs", return_value=context(tmp_path)
    ), patch("frappe_cli.install.wizard.ALL_STEPS", [step]), patch(
        "frappe_cli.install.wizard.time.sleep"
    ) as sleep:
        result = CliRunner().invoke(cli, ["setup", "--task", "production"])
    assert result.exit_code == 1
    assert step.run.call_count == 3
    assert sleep.call_count == 2
    assert state_file.exists()


def test_resume_revalidates_missing_site_without_recreating_it(tmp_path, state_file):
    save_state(InstallState(completed_steps=["site_create"]))
    step = fake_step("site_create")
    with patch(
        "frappe_cli.install.wizard.collect_credentials_for_resume",
        return_value=context(tmp_path),
    ), patch("frappe_cli.install.wizard.ALL_STEPS", [step]):
        result = CliRunner().invoke(cli, ["setup", "--resume"])
    assert result.exit_code == 1
    step.check.assert_called_once()
    step.run.assert_not_called()
    assert "resource is missing" in result.output
    assert state_file.exists()


def test_success_clears_state(tmp_path, state_file):
    step = fake_step()
    with patch(
        "frappe_cli.install.wizard.collect_inputs",
        return_value=context(tmp_path, workflow="custom", selected_steps=[step.name]),
    ), patch("frappe_cli.install.wizard.ALL_STEPS", [step]):
        result = CliRunner().invoke(cli, ["setup", "--task", "production"])
    assert result.exit_code == 0, result.output
    assert not state_file.exists()
    assert "Selected components completed" in result.output
    assert "https://" not in result.output


def test_bench_preview_and_rollback_preserve_existing_directory(tmp_path):
    ctx = context(tmp_path, dry_run=True)
    ctx.bench_path.mkdir()
    marker = ctx.bench_path / "important.txt"
    marker.write_text("keep")
    with patch.object(BenchInitStep, "_run") as run:
        step = BenchInitStep()
        step.run(ctx)
        step.rollback(ctx)
    assert marker.read_text() == "keep"
    assert not list(tmp_path.glob("*.partial-*"))
    assert run.call_args.kwargs["cwd"] == str(tmp_path)


def test_narrow_terminal_progress_remains_readable():
    output = io.StringIO()
    console = Console(file=output, width=42, height=24, color_system=None)
    renderer = StepListRenderer(
        [f"Installation component {index}" for index in range(18)]
    )
    renderer.mark_running("Installation component 6")
    renderer.add_log("An extended log line " * 10)
    console.print(renderer)
    text = output.getvalue()
    assert "Installation component 6" in text
    assert "more steps" in text
    assert "earlier steps" in text
    assert "\x1b[" not in text
    assert max(len(line) for line in text.splitlines()) <= 42


def test_state_roundtrips_custom_plan_and_path(state_file, tmp_path):
    state = InstallState(
        bench_name="demo-bench",
        bench_parent=str(tmp_path),
        selected_steps=["redis"],
        workflow="custom",
        skip_ssl=True,
    )
    save_state(state)
    assert load_state() == state


def test_development_profile_excludes_production_and_ssl(tmp_path, state_file):
    captured = {}

    def collect(console, **kwargs):
        captured.update(kwargs)
        return context(
            tmp_path, dry_run=True, selected_steps=resolve_steps(kwargs["components"])
        )

    with patch("frappe_cli.install.wizard.collect_inputs", side_effect=collect):
        result = CliRunner().invoke(
            cli, ["setup", "--task", "development", "--dry-run"]
        )
    assert result.exit_code == 0, result.output
    assert captured["components"] == ["site_create", "app_get"]
    selected = resolve_steps(captured["components"])
    assert "site_create" in selected
    assert "production_setup" not in selected
    assert "ssl_setup" not in selected
    assert not state_file.exists()


def test_site_creation_preserves_incomplete_directory(tmp_path):
    from frappe_cli.install.steps.site import SiteCreateStep

    ctx = context(tmp_path)
    site = ctx.bench_path / "sites" / ctx.site_name
    site.mkdir(parents=True)
    marker = site / "keep.txt"
    marker.write_text("important")
    with patch("subprocess.run") as run:
        with pytest.raises(StepError, match="already exists"):
            SiteCreateStep().run(ctx)
    run.assert_not_called()
    assert marker.read_text() == "important"


def test_cancel_stops_streamed_child():
    from types import SimpleNamespace

    from frappe_cli.install.steps.base import consume_process

    process = MagicMock()
    process.stdout.readline.side_effect = KeyboardInterrupt
    process.poll.return_value = None
    with pytest.raises(KeyboardInterrupt):
        consume_process(SimpleNamespace(log_fn=None), process, ["bench", "init"])
    process.terminate.assert_called_once()
    process.wait.assert_called_with(timeout=5)


def test_sql_input_is_not_prefixed_with_sudo_password(tmp_path):
    from frappe_cli.install.steps.mariadb import MariaDBSecureStep

    ctx = context(tmp_path)
    payload = b"SELECT 1;\n"
    with patch("frappe_cli.install.steps.base.os.geteuid", return_value=1000), patch(
        "subprocess.run", return_value=MagicMock(returncode=0)
    ) as run:
        MariaDBSecureStep()._sudo_pipe_stdin(ctx, ["mysql"], payload)
    auth, sql = run.call_args_list
    assert auth.args[0] == ["sudo", "-S", "-p", "", "-v"]
    assert auth.kwargs["input"] == b"sudo-secret\n"
    assert sql.args[0] == ["sudo", "-n", "mysql"]
    assert sql.kwargs["input"] == payload


def test_scripted_answers_are_independent_of_sudo_cache(tmp_path):
    from frappe_cli.ssl.secure import Runner

    with patch("frappe_cli.install.steps.base.os.geteuid", return_value=1000), patch(
        "subprocess.run", return_value=MagicMock(returncode=0)
    ) as run:
        Runner("sudo-secret").run(["bench", "setup"], stdin=b"y\ny\n")
    auth, command = run.call_args_list
    assert auth.kwargs["input"] == b"sudo-secret\n"
    assert command.kwargs["input"] == b"y\ny\n"
    assert command.args[0] == ["sudo", "-n", "bench", "setup"]
