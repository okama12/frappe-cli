"""New bench locations come from the server filesystem, without side effects."""

import io
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner
from rich.console import Console

from frappe_cli.cli import cli
from frappe_cli.ui.prompts import _bench_inputs, _choose_parent_directory


def test_browse_server_directories_and_choose_before_naming(tmp_path):
    parent = tmp_path / "deployments"
    parent.mkdir()
    (tmp_path / "notes.txt").write_text("not a directory")
    output = io.StringIO()
    with patch("frappe_cli.ui.terminal.interactive", return_value=True), patch(
        "frappe_cli.ui.prompts.discover_benches", return_value=[]
    ), patch("frappe_cli.ui.prompts.find_bench_root", return_value=None), patch(
        "frappe_cli.ui.terminal.choose", side_effect=["new", str(parent), "use"]
    ) as choose, patch(
        "frappe_cli.ui.terminal.ask", return_value="my-bench"
    ) as ask:
        name, location = _bench_inputs(
            Console(file=output, width=200), {"bench_parent": str(tmp_path)}
        )
        assert choose.call_count == 3
        ask.assert_called_once()
    assert (name, location) == ("my-bench", str(parent))
    listed = choose.call_args_list[1].args[1]
    assert (str(parent), "deployments/") in listed
    assert all("notes.txt" not in label for _, label in listed)
    assert f"Bench location: {parent / name}" in output.getvalue()
    assert not (parent / name).exists()


def test_browse_parent_and_jump_to_relative_path(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    with patch(
        "frappe_cli.ui.terminal.choose", side_effect=["up", "path", "use"]
    ), patch("frappe_cli.ui.terminal.ask_directory", return_value="child"):
        result = _choose_parent_directory(Console(file=io.StringIO()), str(child))
    assert result == str(child)


def test_invalid_jump_and_readonly_selection_allow_recovery(tmp_path):
    output = io.StringIO()
    with patch(
        "frappe_cli.ui.terminal.choose", side_effect=["path", "use", "use"]
    ), patch(
        "frappe_cli.ui.terminal.ask_directory", return_value=str(tmp_path / "missing")
    ), patch(
        "frappe_cli.ui.prompts.os.access", side_effect=[False, True]
    ):
        result = _choose_parent_directory(Console(file=output), str(tmp_path))
    assert result == str(tmp_path)
    assert "existing directory" in output.getvalue()
    assert "write access" in output.getvalue()
    assert not (tmp_path / "missing").exists()


def test_unreadable_directory_can_be_left(tmp_path, monkeypatch):
    child = tmp_path / "restricted"
    child.mkdir()
    original = Path.iterdir

    def iterdir(path):
        if path == child:
            raise PermissionError("no access")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    output = io.StringIO()
    with patch("frappe_cli.ui.terminal.choose", side_effect=["up", "use"]):
        result = _choose_parent_directory(Console(file=output), str(child))
    assert result == str(tmp_path)
    assert "Cannot list this directory" in output.getvalue()


def test_unavailable_previous_location_starts_at_home(tmp_path):
    with patch("frappe_cli.ui.prompts.Path.home", return_value=tmp_path), patch(
        "frappe_cli.ui.terminal.choose", return_value="use"
    ):
        result = _choose_parent_directory(
            Console(file=io.StringIO()), str(tmp_path / "removed")
        )
    assert result == str(tmp_path)


def test_existing_bench_bypasses_location_and_name_prompts(tmp_path):
    bench = tmp_path / "existing-bench"
    with patch("frappe_cli.ui.terminal.interactive", return_value=True), patch(
        "frappe_cli.ui.prompts.discover_benches", return_value=[bench]
    ), patch("frappe_cli.ui.terminal.choose", return_value=str(bench)), patch(
        "frappe_cli.ui.terminal.ask"
    ) as ask:
        assert _bench_inputs(Console(file=io.StringIO()), {}) == (
            bench.name,
            str(tmp_path),
        )
    ask.assert_not_called()


def test_plain_input_asks_location_then_name(tmp_path):
    with patch("frappe_cli.ui.terminal.interactive", return_value=False), patch(
        "frappe_cli.ui.terminal.ask", side_effect=[str(tmp_path), "demo-bench"]
    ) as ask:
        assert _bench_inputs(Console(file=io.StringIO()), {}) == (
            "demo-bench",
            str(tmp_path),
        )
    assert [call.args[1] for call in ask.call_args_list] == [
        "Parent directory",
        "Bench name",
    ]


def test_cancel_browser_does_not_create_bench(tmp_path):
    with patch("frappe_cli.ui.terminal.interactive", return_value=True), patch(
        "frappe_cli.ui.prompts.discover_benches", return_value=[]
    ), patch(
        "frappe_cli.ui.terminal.choose", side_effect=["new", click.Abort()]
    ), patch(
        "frappe_cli.ui.terminal.ask"
    ) as ask:
        with pytest.raises(click.Abort):
            _bench_inputs(Console(file=io.StringIO()), {"bench_parent": str(tmp_path)})
    ask.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_redirected_setup_preview_uses_chosen_server_location(tmp_path):
    answers = "\n".join(
        [str(tmp_path), "demo-bench", "shop.example.com", "version-15", "", "y", ""]
    )
    with patch("frappe_cli.ui.terminal.interactive", return_value=False), patch(
        "frappe_cli.install.wizard.state_exists", return_value=False
    ):
        result = CliRunner().invoke(
            cli, ["setup", "--task", "development", "--dry-run"], input=answers
        )
    assert result.exit_code == 0, result.output
    assert "Bench location:" in result.output
    assert "demo-bench" in result.output
    assert "No installation commands ran" in result.output
    assert list(tmp_path.iterdir()) == []
