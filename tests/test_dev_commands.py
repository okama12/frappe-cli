"""Tests for the dev-workflow commands: use, context, sites, and passthrough."""

from __future__ import annotations

import json
import os
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


# ── fc use ────────────────────────────────────────────────────────────────────


def test_use_outside_bench(tmp_path):
    """fc use should abort when not inside a bench directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["use", "mysite.local"])
    assert result.exit_code != 0
    assert "Not inside a Frappe bench" in result.output


def test_use_site_not_found(tmp_path):
    """fc use should abort when the named site does not exist in the bench."""
    bench = _make_bench(tmp_path)
    runner = CliRunner()
    with patch.dict(os.environ, {}):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            os.chdir(bench)
            result = runner.invoke(cli, ["use", "ghost.local"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_use_writes_fp_yaml(tmp_path):
    """fc use should write the site to .fp.yaml in the bench root."""
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
    """fc use should detect the bench root even from a nested subdirectory."""
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


# ── fc context ────────────────────────────────────────────────────────────────


def test_context_no_bench(tmp_path):
    """fc context should print a helpful message when not inside a bench."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["context"])
    assert result.exit_code == 0
    assert "Not inside a bench" in result.output


def test_context_shows_bench_and_site(tmp_path):
    """fc context should show bench path and active site when set."""
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


# ── fc sites ──────────────────────────────────────────────────────────────────


def test_sites_lists_all(tmp_path):
    """fc sites should list all sites found in the bench."""
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


# ── passthrough: fc migrate (site-scoped) ────────────────────────────────────


def test_migrate_injects_site(tmp_path):
    """fc migrate should run 'bench --site <active> migrate' in the bench root."""
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
    """fc migrate should abort with a helpful message when no site is set."""
    bench = _make_bench(tmp_path)
    runner = CliRunner()
    orig_dir = os.getcwd()
    try:
        os.chdir(bench)
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code != 0
        assert "fcli use" in result.output
    finally:
        os.chdir(orig_dir)


# ── passthrough: fc restart (bench-scoped, no site) ──────────────────────────


def test_restart_does_not_inject_site(tmp_path):
    """fc restart should run 'bench restart' without --site even if a site is active."""
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
