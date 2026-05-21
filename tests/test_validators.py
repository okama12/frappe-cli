"""Tests for the strict identifier validators in :mod:`frappe_cli.utils.validators`.

The validators gate every user-supplied identifier that flows into a path, a
shell command, or an SQL statement. Regressions here would re-open the
critical findings from the security audit, so the bar for coverage is high:

* Allowed inputs are explicitly accepted.
* Disallowed inputs (path traversal, shell metas, NUL, leading dash,
  control chars, RFC1918 hosts, private/loopback IPs) are explicitly
  rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from frappe_cli.utils.errors import ValidationError
from frappe_cli.utils.validators import (
    safe_bench_path,
    validate_bench_name,
    validate_branch_name,
    validate_email,
    validate_git_url,
    validate_port_spec,
    validate_site_name,
)


class TestValidateBenchName:
    @pytest.mark.parametrize(
        "value",
        ["frappe-bench", "test5-bench", "bench_1", "bench.local", "abc123", "B"],
    )
    def test_accepts_valid(self, value: str) -> None:
        assert validate_bench_name(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            ".",
            "..",
            "-leading-dash",
            "../escape",
            "a/b",
            "name with space",
            "name\nnewline",
            "name\x00null",
            "name;rm",
            "name`whoami`",
            "name$(whoami)",
            "name|pipe",
            "a" * 64,
        ],
    )
    def test_rejects_unsafe(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_bench_name(value)


class TestValidateSiteName:
    @pytest.mark.parametrize(
        "value",
        ["example.com", "test5.rashidiokama.com", "dev.local", "test", "a-b.c"],
    )
    def test_accepts_valid(self, value: str) -> None:
        assert validate_site_name(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "-leading.dot",
            "a..b",
            "a/b",
            "name with space",
            "name;rm",
            "name`evil`",
            "a" * 254,
            "label-",  # trailing hyphen
            "-label",  # leading hyphen
        ],
    )
    def test_rejects_unsafe(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_site_name(value)


class TestValidateBranchName:
    @pytest.mark.parametrize(
        "value",
        ["main", "version-15", "feature/foo", "release-1.0+build7"],
    )
    def test_accepts_valid(self, value: str) -> None:
        assert validate_branch_name(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "-leading",
            "name with space",
            "name;injection",
            "a..b",  # git refuses .. in refs
            "a\nb",
        ],
    )
    def test_rejects_unsafe(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_branch_name(value)


class TestValidateEmail:
    @pytest.mark.parametrize("value", ["a@b.co", "user+tag@example.com"])
    def test_accepts_valid(self, value: str) -> None:
        assert validate_email(value) == value

    @pytest.mark.parametrize(
        "value", ["", "not-an-email", "a@b", "a@@b.co", "a b@x.co"]
    )
    def test_rejects_invalid(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_email(value)


class TestValidateGitUrl:
    @pytest.mark.parametrize(
        "value",
        [
            "erpnext",
            "https://github.com/frappe/erpnext",
            "https://github.com/frappe/erpnext.git",
            "git@github.com:owner/repo.git",
            "ssh://git@gitlab.com/owner/repo.git",
        ],
    )
    def test_accepts_valid(self, value: str) -> None:
        assert validate_git_url(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "-upload-pack=cmd",
            "file:///etc/passwd",
            "https://127.0.0.1/repo.git",
            "https://10.0.0.5/repo.git",
            "https://192.168.1.10/repo.git",
            "https://[::1]/repo.git",
        ],
    )
    def test_rejects_invalid(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_git_url(value)


class TestValidatePortSpec:
    @pytest.mark.parametrize("value", ["80", "443/tcp", "5353/udp", "65535/tcp"])
    def test_accepts_valid(self, value: str) -> None:
        assert validate_port_spec(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "0/tcp",
            "70000",
            "22/sctp",
            "80; rm -rf /",
            "80/tcp; reboot",
        ],
    )
    def test_rejects_invalid(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_port_spec(value)


class TestSafeBenchPath:
    def test_under_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        path = safe_bench_path("frappe-bench")
        assert path == (tmp_path / "frappe-bench").resolve()

    def test_rejects_traversal(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        with pytest.raises(ValidationError):
            safe_bench_path("../outside")

    def test_rejects_absolute(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        with pytest.raises(ValidationError):
            safe_bench_path("/etc")
