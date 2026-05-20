"""Tests for the dev-workflow commands: use, context, sites, and passthrough."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from frappe_cli.cli import cli

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_bench(tmp_path: Path, sites: list[str] | None = None) -> Path:
    """Create a minimal fake bench directory tree under *tmp_path*."""
    bench = tmp_path / "test-bench"
    (bench / "apps").mkdir(parents=True)
    (bench / "sites").mkdir(parents=True)
    for site in sites or []:
        site_dir = bench / "sites" / site
        site_dir.mkdir()
        (site_dir / "site_config.json").write_text(json.dumps({}))
    return bench


# ── fp use ────────────────────────────────────────────────────────────────────


def test_use_outside_bench(tmp_path):
    """fp use should abort when not inside a bench directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["use", "mysite.local"])
    assert result.exit_code != 0
    assert "Not inside a Frappe bench" in result.output


def test_use_site_not_found(tmp_path):
    """fp use should abort when the named site does not exist in the bench."""
    bench = _make_bench(tmp_path)
    runner = CliRunner()
    with patch.dict(os.environ, {}):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            os.chdir(bench)
            result = runner.invoke(cli, ["use", "ghost.local"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_use_writes_fp_yaml(tmp_path):
    """fp use should write the site to .fp.yaml in the bench root."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        result = runner.invoke(cli, ["use", "dev.local"])
        assert result.exit_code == 0, result.output
        fp_yaml = bench / ".fp.yaml"
        assert fp_yaml.exists()
        data = yaml.safe_load(fp_yaml.read_text())
        assert data["site"] == "dev.local"
    finally:
        os.chdir(orig_dir)


def test_use_works_from_subdirectory(tmp_path):
    """fp use should detect the bench root even from a nested subdirectory."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    subdir = bench / "apps" / "my_app"
    subdir.mkdir(parents=True)
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(subdir)
        result = runner.invoke(cli, ["use", "dev.local"])
        assert result.exit_code == 0, result.output
        data = yaml.safe_load((bench / ".fp.yaml").read_text())
        assert data["site"] == "dev.local"
    finally:
        os.chdir(orig_dir)


# ── fp context ────────────────────────────────────────────────────────────────


def test_context_no_bench(tmp_path):
    """fp context should print a helpful message when not inside a bench."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["context"])
    assert result.exit_code == 0
    assert "Not inside a bench" in result.output


def test_context_shows_bench_and_site(tmp_path):
    """fp context should show bench path and active site when set."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    fp = bench / ".fp.yaml"
    fp.write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        result = runner.invoke(cli, ["context"])
        assert result.exit_code == 0, result.output
        # Output shows the bench path (possibly truncated by Rich) and the active site.
        assert "dev.local" in result.output
        # The "Bench" label is always present in the table row.
        assert "Bench" in result.output
    finally:
        os.chdir(orig_dir)


# ── fp sites ──────────────────────────────────────────────────────────────────


def test_sites_lists_all(tmp_path):
    """fp sites should list all sites found in the bench."""
    bench = _make_bench(tmp_path, sites=["alpha.local", "beta.local"])
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        result = runner.invoke(cli, ["sites"])
        assert result.exit_code == 0, result.output
        assert "alpha.local" in result.output
        assert "beta.local" in result.output
    finally:
        os.chdir(orig_dir)


# ── passthrough: fp migrate (site-scoped) ────────────────────────────────────


def test_migrate_injects_site(tmp_path):
    """fp migrate should run 'bench --site <active> migrate' in the bench root."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    (bench / ".fp.yaml").write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["bench", "--site", "dev.local", "migrate"]
    finally:
        os.chdir(orig_dir)


def test_migrate_no_active_site(tmp_path):
    """fp migrate should abort with a helpful message when no site is set."""
    bench = _make_bench(tmp_path)
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code != 0
        assert "fp use" in result.output
    finally:
        os.chdir(orig_dir)


# ── fp deploy ─────────────────────────────────────────────────────────────────


def test_deploy_runs_pull_migrate_restart_in_order(tmp_path):
    """fp deploy should run git pull, migrate, then restart — in that order."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    app_dir = bench / "apps" / "my_app"
    app_dir.mkdir(parents=True)
    (bench / ".fp.yaml").write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    calls: list[tuple[list[str], str]] = []
    try:
        os.chdir(app_dir)
        with patch("subprocess.run") as mock_run:

            def _capture(cmd, **kwargs):
                calls.append((list(cmd), kwargs.get("cwd", "")))
                if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
                    return subprocess.CompletedProcess([], 0, stdout="true\n")
                return subprocess.CompletedProcess([], 0)

            mock_run.side_effect = _capture

            result = runner.invoke(cli, ["deploy"])
        assert result.exit_code == 0, result.output
        assert "Deploy complete" in result.output
        assert calls[0][0] == ["git", "rev-parse", "--is-inside-work-tree"]
        assert calls[1][0] == ["git", "pull"]
        assert calls[2][0] == ["bench", "--site", "dev.local", "migrate"]
        assert calls[3][0] == ["bench", "restart"]
    finally:
        os.chdir(orig_dir)


def test_deploy_stops_on_migrate_failure(tmp_path):
    """fp deploy should not restart if migrate fails."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    app_dir = bench / "apps" / "my_app"
    app_dir.mkdir(parents=True)
    (bench / ".fp.yaml").write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    restart_called = False
    try:
        os.chdir(app_dir)

        def _side_effect(cmd, **kwargs):
            nonlocal restart_called
            if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
                return subprocess.CompletedProcess([], 0, stdout="true\n")
            if cmd[:2] == ["git", "pull"]:
                return subprocess.CompletedProcess([], 0)
            if cmd[:2] == ["bench", "--site"]:
                return subprocess.CompletedProcess([], 1)
            if cmd == ["bench", "restart"]:
                restart_called = True
                return subprocess.CompletedProcess([], 0)
            return subprocess.CompletedProcess([], 0)

        with patch("subprocess.run", side_effect=_side_effect):
            result = runner.invoke(cli, ["deploy"])
        assert result.exit_code == 1
        assert restart_called is False
    finally:
        os.chdir(orig_dir)


def test_deploy_no_pull_skips_git(tmp_path):
    """fp deploy --no-pull should skip git pull."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    (bench / ".fp.yaml").write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["deploy", "--no-pull"])
        assert result.exit_code == 0, result.output
        cmds = [call[0][0] for call in mock_run.call_args_list]
        assert cmds[0] == ["bench", "--site", "dev.local", "migrate"]
        assert cmds[1] == ["bench", "restart"]
        assert not any(cmd[0] == "git" for cmd in cmds)
    finally:
        os.chdir(orig_dir)


def test_deploy_requires_git_repo_without_no_pull(tmp_path):
    """fp deploy should abort when cwd is not a git repo."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    (bench / ".fp.yaml").write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 1)
            result = runner.invoke(cli, ["deploy"])
        assert result.exit_code != 0
        assert "git repository" in result.output.lower()
    finally:
        os.chdir(orig_dir)


def test_restart_does_not_inject_site(tmp_path):
    """fp restart should run 'bench restart' without --site even if a site is active."""
    bench = _make_bench(tmp_path, sites=["dev.local"])
    (bench / ".fp.yaml").write_text(yaml.dump({"site": "dev.local"}))
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["restart"])
        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert "--site" not in cmd
        assert cmd == ["bench", "restart"]
    finally:
        os.chdir(orig_dir)
