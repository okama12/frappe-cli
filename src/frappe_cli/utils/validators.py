import ipaddress
import os
import re
from pathlib import Path
from typing import Callable, List, Optional, TypeVar, Union, cast
from urllib.parse import urlparse

import click

from .errors import ResourceNotFoundError, ValidationError

T = TypeVar("T")

# ── Identifier patterns (strict allowlists) ─────────────────────────────────
# Bench/app directory names: letters, digits, hyphen, underscore, dot.
# Must start with a letter or digit; max 63 chars (filesystem-friendly).
_BENCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")

# Branch names: git-friendly subset. No spaces, no shell metas, no leading dash.
_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+-]{0,127}$")

# FQDN (RFC 1035-ish): each label 1-63 chars; total <= 253; allow trailing dot.
# Single-label hostnames (e.g. "test", "localhost") accepted too.
_FQDN_LABEL_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")

# RFC 5322-lite email pattern. Good enough for Let's Encrypt registration.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_path_exists(
    path: Union[str, Path], error_message: Optional[str] = None
) -> Path:
    """
    Validate that a path exists.

    Args:
        path: The path to validate
        error_message: Custom error message if validation fails

    Returns:
        The validated path as a Path object

    Raises:
        ResourceNotFoundError: If the path doesn't exist
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise ResourceNotFoundError(error_message or f"Path does not exist: {path}")

    return path_obj


def validate_directory_exists(
    path: Union[str, Path], error_message: Optional[str] = None
) -> Path:
    """
    Validate that a directory exists.

    Args:
        path: The directory path to validate
        error_message: Custom error message if validation fails

    Returns:
        The validated directory path as a Path object

    Raises:
        ResourceNotFoundError: If the directory doesn't exist
        ValidationError: If the path exists but is not a directory
    """
    path_obj = validate_path_exists(path, error_message)
    if not path_obj.is_dir():
        raise ValidationError(error_message or f"Path is not a directory: {path}")

    return path_obj


def validate_file_exists(
    path: Union[str, Path], error_message: Optional[str] = None
) -> Path:
    """
    Validate that a file exists.

    Args:
        path: The file path to validate
        error_message: Custom error message if validation fails

    Returns:
        The validated file path as a Path object

    Raises:
        ResourceNotFoundError: If the file doesn't exist
        ValidationError: If the path exists but is not a file
    """
    path_obj = validate_path_exists(path, error_message)
    if not path_obj.is_file():
        raise ValidationError(error_message or f"Path is not a file: {path}")

    return path_obj


def validate_sudo_access() -> None:
    """
    Validate that the current user has sudo access.

    Raises:
        ValidationError: If the user doesn't have sudo access
    """
    if os.geteuid() != 0:
        raise ValidationError(
            "This command requires sudo access", "Please run this command with sudo"
        )


def validate_pattern(
    value: str, pattern: str, error_message: Optional[str] = None
) -> str:
    """
    Validate that a string matches a regular expression pattern.

    Args:
        value: The string to validate
        pattern: The regular expression pattern to match
        error_message: Custom error message if validation fails

    Returns:
        The validated string

    Raises:
        ValidationError: If the string doesn't match the pattern
    """
    if not re.match(pattern, value):
        raise ValidationError(
            error_message or f"Value '{value}' does not match pattern '{pattern}'"
        )

    return value


def validate_choice(
    value: T, choices: List[T], error_message: Optional[str] = None
) -> T:
    """
    Validate that a value is one of the allowed choices.

    Args:
        value: The value to validate
        choices: The list of allowed choices
        error_message: Custom error message if validation fails

    Returns:
        The validated value

    Raises:
        ValidationError: If the value is not in the list of choices
    """
    if value not in choices:
        choices_str = ", ".join(str(c) for c in choices)
        raise ValidationError(
            error_message
            or f"Value '{value}' is not one of the allowed choices: {choices_str}"
        )

    return value


def validate_not_empty(value: str, error_message: Optional[str] = None) -> str:
    """
    Validate that a string is not empty.

    Args:
        value: The string to validate
        error_message: Custom error message if validation fails

    Returns:
        The validated string

    Raises:
        ValidationError: If the string is empty
    """
    if not value.strip():
        raise ValidationError(error_message or "Value cannot be empty")

    return value


# ── Identifier validators (strict allowlists for names that flow into paths) ──


def validate_bench_name(value: str) -> str:
    """Validate a bench directory name.

    Allowed: letters, digits, hyphen, underscore, dot; must start with a
    letter/digit; max 63 characters. This name is concatenated into paths under
    ``$HOME`` and ``/etc/{nginx,supervisor}/conf.d/`` — values that contain
    ``/``, ``..``, NUL, or other shell metacharacters are rejected to prevent
    path traversal and command injection.
    """
    if not value:
        raise ValidationError("Bench name cannot be empty")
    if not _BENCH_NAME_RE.match(value):
        raise ValidationError(
            f"Invalid bench name '{value}'. "
            "Use letters, digits, hyphen, underscore, or dot; "
            "must start with a letter or digit and be ≤63 characters."
        )
    if value in {".", ".."}:
        raise ValidationError("Bench name cannot be '.' or '..'")
    return value


def validate_site_name(value: str) -> str:
    """Validate a Frappe site name (FQDN-like).

    Site names become MariaDB DB names, nginx server_name, and on-disk paths.
    Accepts FQDNs (``site.example.com``) and single-label hostnames
    (``dev.local``, ``test``). Rejects path separators, shell metas, and
    leading/trailing dots/dashes.
    """
    if not value:
        raise ValidationError("Site name cannot be empty")
    if len(value) > 253:
        raise ValidationError("Site name is too long (max 253 characters)")
    value = value.rstrip(".")
    labels = value.split(".")
    if not labels:
        raise ValidationError(f"Invalid site name '{value}'")
    for label in labels:
        if not _FQDN_LABEL_RE.match(label):
            raise ValidationError(
                f"Invalid site name '{value}': label '{label}' contains "
                "invalid characters (allowed: letters, digits, hyphen; "
                "no leading or trailing hyphen; ≤63 characters per label)."
            )
    return value


def validate_branch_name(value: str) -> str:
    """Validate a git branch name."""
    if not value:
        raise ValidationError("Branch name cannot be empty")
    if not _BRANCH_NAME_RE.match(value):
        raise ValidationError(
            f"Invalid branch name '{value}'. "
            "Use letters, digits, dot, slash, plus, hyphen, or underscore; "
            "must start with a letter or digit."
        )
    if ".." in value:
        raise ValidationError(f"Branch name '{value}' cannot contain '..'")
    return value


def validate_email(value: str) -> str:
    """Validate an email address (Let's Encrypt registration etc.)."""
    if not value:
        raise ValidationError("Email cannot be empty")
    if not _EMAIL_RE.match(value):
        raise ValidationError(f"Invalid email address: '{value}'")
    return value


def validate_git_url(value: str) -> str:
    """Validate a git URL used with ``git ls-remote`` or ``bench get-app``.

    Allowed schemes/forms:
    - ``https://<host>/<path>``
    - ``http://<host>/<path>`` (warned about, but accepted for completeness)
    - ``git@<host>:<owner>/<repo>(.git)``
    - bare short names like ``erpnext`` (resolved by ``bench get-app`` to
      the official Frappe org)

    Rejected:
    - ``file://``, ``ssh://`` to arbitrary hosts, ``-`` leading (option-style)
    - host that resolves to a literal private/loopback IP
    """
    if not value:
        raise ValidationError("App URL cannot be empty")
    if value.startswith("-"):
        raise ValidationError(f"Invalid app URL '{value}' (cannot start with '-')")

    # Short app name (resolved by bench to github.com/frappe/<name>).
    if "/" not in value and "@" not in value and ":" not in value:
        if not _BENCH_NAME_RE.match(value):
            raise ValidationError(
                f"Invalid short app name '{value}'. Use letters, digits, "
                "hyphen, underscore, or dot."
            )
        return value

    # SCP-style: git@host:owner/repo
    if value.startswith("git@") or re.match(r"^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:", value):
        return value

    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"https", "http", "ssh", "git"}:
        raise ValidationError(
            f"Unsupported URL scheme '{scheme}' in '{value}'. "
            "Use https://, ssh://, or the git@host:owner/repo form."
        )
    host = parsed.hostname or ""
    if not host:
        raise ValidationError(f"App URL '{value}' has no host component")

    # Block hosts that are literal private/loopback IPs.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_private or ip.is_link_local:
            raise ValidationError(
                f"App URL host '{host}' resolves to a private/loopback IP; "
                "refusing to fetch from internal addresses."
            )
    except ValueError:
        pass  # hostname, not a literal IP — fine
    return value


def validate_port_spec(value: str) -> str:
    """Validate a UFW port/protocol entry like ``2222/tcp`` or ``80``."""
    if not value:
        raise ValidationError("Port cannot be empty")
    if not re.match(r"^\d{1,5}(/(tcp|udp))?$", value):
        raise ValidationError(
            f"Invalid port spec '{value}'. Use NNN or NNN/tcp or NNN/udp " "(0–65535)."
        )
    port = int(value.split("/", 1)[0])
    if not 0 < port <= 65535:
        raise ValidationError(f"Port {port} out of range (1–65535)")
    return value


def safe_bench_path(bench_name: str, home: Optional[Path] = None) -> Path:
    """Return a resolved path under ``$HOME`` for *bench_name*, or raise.

    Combines validation + resolution + boundary check. Use this anywhere a
    user-supplied bench name is about to become a real filesystem operation.
    """
    validate_bench_name(bench_name)
    base = (home or Path.home()).resolve()
    candidate = (base / bench_name).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValidationError(
            f"Bench path {candidate} escapes home directory {base}"
        ) from exc
    return candidate


def click_path_exists(
    exists: bool = True,
    file_okay: bool = True,
    dir_okay: bool = True,
    readable: bool = True,
    resolve_path: bool = True,
) -> Callable[[click.Context, click.Parameter, str], Path]:
    """
    Click parameter type for validating paths.

    Args:
        exists: Whether the path must exist
        file_okay: Whether files are allowed
        dir_okay: Whether directories are allowed
        readable: Whether the path must be readable
        resolve_path: Whether to resolve the path

    Returns:
        A Click parameter type function
    """

    def _validate_path(ctx: click.Context, param: click.Parameter, value: str) -> Path:
        if not value:
            return cast(Path, value)

        path = Path(value)
        if resolve_path:
            path = path.resolve()

        if exists and not path.exists():
            raise click.BadParameter(f"Path does not exist: {value}")

        if not file_okay and path.is_file():
            raise click.BadParameter(f"Expected directory, got file: {value}")

        if not dir_okay and path.is_dir():
            raise click.BadParameter(f"Expected file, got directory: {value}")

        if readable and path.exists() and not os.access(path, os.R_OK):
            raise click.BadParameter(f"Path is not readable: {value}")

        return path

    return _validate_path
