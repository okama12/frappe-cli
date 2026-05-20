"""Helpers for detecting Frappe app type and resolving the best branch.

Key functions
-------------
is_official_frappe_app(url)
    Returns True for github.com/frappe/<name> URLs and short names (erpnext, hrms …).

resolve_app_branch(url, frappe_branch, *, timeout)
    Best-effort remote branch resolver:
    - Official Frappe apps  → frappe_branch  (no network call)
    - Custom apps           → try git ls-remote; prefer frappe_branch if present,
                              else main, else develop, else None.
    Returns (branch: str, hint: str | None)
    hint is non-empty when the user should be told something (private repo, etc.)
"""

from __future__ import annotations

import subprocess
from typing import Optional

# Official apps hosted under github.com/frappe/<name>
_OFFICIAL_FRAPPE_APPS: frozenset[str] = frozenset(
    [
        "erpnext",
        "hrms",
        "payments",
        "education",
        "healthcare",
        "lending",
        "wiki",
        "builder",
        "crm",
        "helpdesk",
        "drive",
        "insights",
        "gameplan",
    ]
)

_BRANCH_PRIORITY = ("version-", "main", "master", "develop")

# Message shown when branch detection fails for a custom app.
PRIVATE_REPO_HINT = (
    "Could not detect remote branches (private repo or network error).\n"
    "  If this is a private repo, ensure SSH keys or Git credentials are "
    "configured\n"
    "  (prefer git@github.com:org/repo.git over HTTPS for private repos)."
)


def is_official_frappe_app(url: str) -> bool:
    """Return True when *url* refers to an official app under github.com/frappe/."""
    url = url.strip().rstrip("/").removesuffix(".git").lower()

    # Short name like "erpnext"
    if "/" not in url:
        return url in _OFFICIAL_FRAPPE_APPS

    # URL pattern: github.com/frappe/<name>  or  https://github.com/frappe/<name>
    # Normalise: strip scheme + host
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if url.startswith(prefix):
            path = url[len(prefix) :]
            break
    else:
        return False

    parts = path.split("/")
    if len(parts) < 2:
        return False
    org, name = parts[0], parts[1]
    return org == "frappe" and name in _OFFICIAL_FRAPPE_APPS


def list_remote_branches(url: str, *, timeout: int = 10) -> Optional[list[str]]:
    """Return the list of branch names from *url* via ``git ls-remote``.

    Returns None on any failure (auth error, network, timeout, git not on PATH).
    Never raises.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", url],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return None
        branches: list[str] = []
        for line in result.stdout.splitlines():
            # lines: "<sha>\trefs/heads/<branch>"
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[1].startswith("refs/heads/"):
                branches.append(parts[1][len("refs/heads/") :])
        return branches if branches else None
    except Exception:
        return None


def resolve_app_branch(
    url: str,
    frappe_branch: str,
    *,
    timeout: int = 10,
) -> tuple[str, Optional[str]]:
    """Return *(branch, hint)* for a given app URL.

    - Official Frappe app: (frappe_branch, None) — no network call.
    - Custom app, detection succeeds: best branch, no hint.
    - Custom app, detection fails: ("main", PRIVATE_REPO_HINT).

    Branch priority for custom apps with remote detection:
      1. frappe_branch if present (e.g. version-15)
      2. main
      3. master
      4. develop
      5. alphabetically first branch (last resort)
    """
    if is_official_frappe_app(url):
        return frappe_branch, None

    # Custom / third-party app — try to detect.
    branches = list_remote_branches(url, timeout=timeout)
    if branches is None:
        return "main", PRIVATE_REPO_HINT

    # Priority selection.
    branch_set = set(branches)

    # Exact match for frappe_branch first.
    if frappe_branch in branch_set:
        return frappe_branch, None

    for candidate in ("main", "master", "develop"):
        if candidate in branch_set:
            return candidate, None

    # Fall back to alphabetical first — at least it will work.
    return sorted(branches)[0], None
