"""Tests for frappe_cli.utils.git_repo."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from frappe_cli.utils.git_repo import (
    PRIVATE_REPO_HINT,
    is_official_frappe_app,
    list_remote_branches,
    resolve_app_branch,
)

# ── is_official_frappe_app ─────────────────────────────────────────────────────


class TestIsOfficialFrappeApp:
    @pytest.mark.parametrize(
        "url",
        [
            "erpnext",
            "hrms",
            "payments",
            "https://github.com/frappe/erpnext",
            "https://github.com/frappe/erpnext.git",
            "http://github.com/frappe/hrms",
            "git@github.com:frappe/erpnext",
            "git@github.com:frappe/erpnext.git",
        ],
    )
    def test_official_apps_return_true(self, url):
        assert is_official_frappe_app(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "vsd_fleet_ms",
            "https://github.com/myorg/vsd_fleet_ms",
            "https://github.com/myorg/vsd_fleet_ms.git",
            "git@github.com:myorg/custom_app.git",
            "https://github.com/frappe/unknown_app",
            "",
        ],
    )
    def test_custom_apps_return_false(self, url):
        assert is_official_frappe_app(url) is False


# ── list_remote_branches ───────────────────────────────────────────────────────


class TestListRemoteBranches:
    def test_returns_branches_on_success(self):
        mock_output = (
            "abc123\trefs/heads/main\n"
            "def456\trefs/heads/develop\n"
            "789abc\trefs/heads/version-15\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=mock_output, stderr=""
            )
            result = list_remote_branches("https://github.com/org/repo")
        assert result == ["main", "develop", "version-15"]

    def test_returns_none_on_nonzero_exit(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 128, stdout="", stderr="fatal: not found"
            )
            result = list_remote_branches("https://github.com/org/private")
        assert result is None

    def test_returns_none_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            result = list_remote_branches("https://github.com/org/repo")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("subprocess.run", side_effect=OSError("git not found")):
            result = list_remote_branches("https://github.com/org/repo")
        assert result is None

    def test_returns_none_when_no_branches(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="", stderr=""
            )
            result = list_remote_branches("https://github.com/org/repo")
        assert result is None


# ── resolve_app_branch ─────────────────────────────────────────────────────────


class TestResolveAppBranch:
    def test_official_app_returns_frappe_branch(self):
        branch, hint = resolve_app_branch(
            "https://github.com/frappe/erpnext", "version-15"
        )
        assert branch == "version-15"
        assert hint is None

    def test_official_app_short_name(self):
        branch, hint = resolve_app_branch("hrms", "version-15")
        assert branch == "version-15"
        assert hint is None

    def test_custom_app_detection_fails_returns_main_and_hint(self):
        with patch("frappe_cli.utils.git_repo.list_remote_branches", return_value=None):
            branch, hint = resolve_app_branch(
                "https://github.com/myorg/vsd_fleet_ms", "version-15"
            )
        assert branch == "main"
        assert hint == PRIVATE_REPO_HINT

    def test_custom_app_frappe_branch_exists_in_remote(self):
        with patch(
            "frappe_cli.utils.git_repo.list_remote_branches",
            return_value=["main", "develop", "version-15"],
        ):
            branch, hint = resolve_app_branch(
                "https://github.com/myorg/custom", "version-15"
            )
        assert branch == "version-15"
        assert hint is None

    def test_custom_app_prefers_main_when_no_frappe_branch(self):
        with patch(
            "frappe_cli.utils.git_repo.list_remote_branches",
            return_value=["develop", "main", "feature-x"],
        ):
            branch, hint = resolve_app_branch(
                "https://github.com/myorg/custom", "version-15"
            )
        assert branch == "main"
        assert hint is None

    def test_custom_app_prefers_develop_over_other(self):
        with patch(
            "frappe_cli.utils.git_repo.list_remote_branches",
            return_value=["develop", "feature-x"],
        ):
            branch, hint = resolve_app_branch(
                "https://github.com/myorg/custom", "version-15"
            )
        assert branch == "develop"
        assert hint is None

    def test_custom_app_falls_back_to_first_alphabetical(self):
        with patch(
            "frappe_cli.utils.git_repo.list_remote_branches",
            return_value=["zebra-branch", "alpha-branch"],
        ):
            branch, hint = resolve_app_branch(
                "https://github.com/myorg/custom", "version-15"
            )
        assert branch == "alpha-branch"
        assert hint is None

    def test_official_app_no_network_call(self):
        """Official apps must NOT make any subprocess calls."""
        with patch("subprocess.run") as mock_run:
            resolve_app_branch("erpnext", "version-15")
        mock_run.assert_not_called()
