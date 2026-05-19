"""Smoke tests for the wizard banner / success panel / about command.

These don't validate exact formatting (Rich layout decisions can shift),
they only assert the key credit strings are present so the author
attribution survives future refactors.
"""

import io

from click.testing import CliRunner
from rich.console import Console

import frappe_cli.cli as cli
from frappe_cli.install.context import InstallContext
from frappe_cli.ui.panels import print_error, print_header, print_success


def _render(fn, *args, **kwargs) -> str:
    """Capture Rich output to a string buffer (no ANSI/colors)."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, color_system=None, width=120)
    fn(console, *args, **kwargs)
    return buf.getvalue()


def _make_ctx(skip_ssl: bool = False) -> InstallContext:
    return InstallContext(
        bench_name="my-bench",
        site_name="erp.example.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15",
        sudo_password="",
        mariadb_root_password="",
        admin_password="",
        ssl_email="you@example.com",
        ubuntu_version="24.04",
        dry_run=False,
        skip_ssl=skip_ssl,
    )


# ── banner ───────────────────────────────────────────────────────────────────


class TestPrintHeader:
    def test_includes_product_name_and_tagline(self):
        out = _render(print_header)
        assert "Frappe CLI" in out
        assert "Production Server Installer" in out

    def test_credits_author_name_and_country(self):
        out = _render(print_header)
        assert "Rashidi Okama" in out
        assert "Tanzania" in out

    def test_links_to_github_and_website(self):
        out = _render(print_header)
        assert "github.com/okama12" in out
        assert "rashidiokama.com" in out

    def test_does_not_leak_email(self):
        """User explicitly asked not to include email in the banner."""
        out = _render(print_header)
        assert "@" not in out, f"Banner unexpectedly contains '@':\n{out}"


# ── success panel ────────────────────────────────────────────────────────────


class TestPrintSuccess:
    def test_https_url_when_ssl_enabled(self):
        out = _render(print_success, _make_ctx(skip_ssl=False))
        assert "https://erp.example.com" in out

    def test_http_url_and_skip_ssl_note_when_disabled(self):
        out = _render(print_success, _make_ctx(skip_ssl=True))
        assert "http://erp.example.com" in out
        assert "--skip-ssl" in out

    def test_includes_attribution_and_repo_link(self):
        out = _render(print_success, _make_ctx())
        assert "Rashidi Okama" in out
        assert "Tanzania" in out
        assert "github.com/okama12/frappe-cli" in out

    def test_attribution_uses_soft_phrasing(self):
        out = _render(print_success, _make_ctx())
        # The nudge should be gentle, not pushy — check the actual wording.
        assert "if this saved you time" in out


# ── error panel (unchanged behaviour smoke test) ─────────────────────────────


class TestPrintError:
    def test_shows_step_and_resume_hint(self):
        out = _render(
            print_error, "Configure SSL", "Command failed", hint="cert path not found"
        )
        assert "Configure SSL" in out
        assert "Command failed" in out
        assert "frappe install wizard --resume" in out


# ── frappe about ─────────────────────────────────────────────────────────────


class TestAboutCommand:
    def test_about_help_renders(self):
        runner = CliRunner()
        result = runner.invoke(cli.cli, ["about", "--help"])
        assert result.exit_code == 0
        assert "author" in result.output.lower() or "credits" in result.output.lower()

    def test_about_command_shows_full_credits(self):
        runner = CliRunner()
        result = runner.invoke(cli.cli, ["about"])
        assert result.exit_code == 0
        for expected in [
            "Rashidi Okama",
            "Tanzania",
            "github.com/okama12",
            "rashidiokama.com",
            "pypi.org/project/frappe-cli",
            "MIT",
        ]:
            assert expected in result.output, f"`about` missing {expected!r}"

    def test_about_command_invites_star(self):
        runner = CliRunner()
        result = runner.invoke(cli.cli, ["about"])
        assert "star the repo" in result.output.lower()
