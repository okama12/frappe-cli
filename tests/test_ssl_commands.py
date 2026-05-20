import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import frappe_cli.cli as cli
import frappe_cli.ssl.list_certs  # noqa: F401 — populate sys.modules
import frappe_cli.ssl.setup  # noqa: F401 — populate sys.modules

# The package __init__ does `from .setup import setup`, which shadows the
# `setup` MODULE attribute on `frappe_cli.ssl` with the click command of the
# same name. Reach the underlying module via sys.modules so patch.object works.
ssl_setup_mod = sys.modules["frappe_cli.ssl.setup"]
ssl_list_mod = sys.modules["frappe_cli.ssl.list_certs"]


def test_ssl_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["ssl", "--help"])
    assert result.exit_code == 0
    assert "SSL/HTTPS management commands" in result.output or "SSL" in result.output


def test_ssl_setup_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["ssl", "setup", "--help"])
    assert result.exit_code == 0
    # Docstring/help mentions Let's Encrypt
    assert "Let's Encrypt" in result.output


def test_ssl_list_help():
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["ssl", "list", "--help"])
    assert result.exit_code == 0


# ── _find_bench_for_site (auto-detection) ────────────────────────────────────


class TestFindBenchForSite:
    def test_explicit_bench_found(self, tmp_path):
        from frappe_cli.ssl.setup import _find_bench_for_site

        (tmp_path / "test5-bench" / "sites" / "test5.example.com").mkdir(parents=True)
        (
            tmp_path
            / "test5-bench"
            / "sites"
            / "test5.example.com"
            / "site_config.json"
        ).write_text("{}")

        with patch("pathlib.Path.home", return_value=tmp_path):
            bench = _find_bench_for_site("test5.example.com", "test5-bench")
        assert bench.name == "test5-bench"

    def test_auto_detect_scans_home(self, tmp_path):
        from frappe_cli.ssl.setup import _find_bench_for_site

        # Two benches, only one owns the site
        (tmp_path / "other-bench" / "sites" / "other.example.com").mkdir(parents=True)
        (
            tmp_path
            / "other-bench"
            / "sites"
            / "other.example.com"
            / "site_config.json"
        ).write_text("{}")
        (tmp_path / "test5-bench" / "sites" / "test5.example.com").mkdir(parents=True)
        (
            tmp_path
            / "test5-bench"
            / "sites"
            / "test5.example.com"
            / "site_config.json"
        ).write_text("{}")

        with patch("pathlib.Path.home", return_value=tmp_path):
            bench = _find_bench_for_site("test5.example.com")
        assert bench.name == "test5-bench"

    def test_raises_when_site_missing(self, tmp_path):
        import click as _click

        from frappe_cli.ssl.setup import _find_bench_for_site

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            pytest.raises(_click.ClickException) as exc,
        ):
            _find_bench_for_site("nonexistent.example.com")
        assert "nonexistent.example.com" in str(exc.value.message)

    def test_raises_when_explicit_bench_lacks_site(self, tmp_path):
        import click as _click

        from frappe_cli.ssl.setup import _find_bench_for_site

        (tmp_path / "test5-bench" / "sites").mkdir(parents=True)
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            pytest.raises(_click.ClickException),
        ):
            _find_bench_for_site("missing.example.com", "test5-bench")


# ── _cert_exists ──────────────────────────────────────────────────────────────


class TestSslSetupCertExists:
    def test_true_when_path_exists(self):
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        with patch.object(ssl_setup_mod, "Path", return_value=fake_path):
            assert ssl_setup_mod._cert_exists("test5.example.com", "pw") is True

    def test_falls_back_to_sudo_test_on_permission_error(self):
        fake_path = MagicMock()
        fake_path.exists.side_effect = PermissionError("denied")
        with (
            patch.object(ssl_setup_mod, "Path", return_value=fake_path),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            assert ssl_setup_mod._cert_exists("test5.example.com", "pw") is True
        # Verify sudo test -f was invoked
        invoked = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "test" in invoked and "-f" in invoked


# ── frappe ssl setup — end-to-end via Click ──────────────────────────────────


class TestSslSetupCommand:
    def test_skips_when_cert_already_present(self, tmp_path):
        """Should not invoke bench setup lets-encrypt if cert exists."""
        (tmp_path / "test5-bench" / "sites" / "test5.example.com").mkdir(parents=True)
        (
            tmp_path
            / "test5-bench"
            / "sites"
            / "test5.example.com"
            / "site_config.json"
        ).write_text("{}")

        runner = CliRunner()
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("getpass.getpass", return_value="pw"),
            patch.object(ssl_setup_mod, "_cert_exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            result = runner.invoke(
                cli.cli,
                ["ssl", "setup", "--site-name", "test5.example.com"],
            )
        assert result.exit_code == 0
        assert "already exists" in result.output
        # `bench setup lets-encrypt` was NOT invoked
        joined = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "lets-encrypt" not in joined

    def test_invokes_bench_setup_lets_encrypt(self, tmp_path):
        (tmp_path / "my-bench" / "sites" / "my.example.com").mkdir(parents=True)
        (
            tmp_path / "my-bench" / "sites" / "my.example.com" / "site_config.json"
        ).write_text("{}")

        cert_exists_calls = iter([False, True])

        runner = CliRunner()
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("getpass.getpass", return_value="pw"),
            patch.object(
                ssl_setup_mod,
                "_cert_exists",
                side_effect=lambda *a, **kw: next(cert_exists_calls),
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            result = runner.invoke(
                cli.cli,
                ["ssl", "setup", "--site-name", "my.example.com"],
            )
        assert result.exit_code == 0, result.output

        joined = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "setup" in joined and "lets-encrypt" in joined
        assert "my.example.com" in joined


# ── frappe ssl list ───────────────────────────────────────────────────────────


class TestSslListCommand:
    def test_lists_sites_and_marks_missing(self, tmp_path):
        for bench, site in [
            ("test5-bench", "test5.example.com"),
            ("test6-bench", "test6.example.com"),
        ]:
            (tmp_path / bench / "sites" / site).mkdir(parents=True)
            (tmp_path / bench / "sites" / site / "site_config.json").write_text("{}")

        runner = CliRunner()
        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch.object(
                ssl_list_mod,
                "_has_cert",
                side_effect=lambda site, pw: site == "test5.example.com",
            ),
        ):
            result = runner.invoke(cli.cli, ["ssl", "list", "--no-sudo"])
        assert result.exit_code == 0, result.output
        assert "test5.example.com" in result.output
        assert "test6.example.com" in result.output
        # Rich may wrap the hint column; check both site name and the
        # suggested-command preamble appear somewhere in the output.
        assert "fp ssl setup --site-name" in result.output
        assert "1 site(s) without SSL" in result.output
