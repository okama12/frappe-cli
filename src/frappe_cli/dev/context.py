"""Bench detection and per-bench active-site context.

State is stored in ``<bench_root>/.fp.yaml`` (one key: ``site``).
This file is completely separate from ``~/.frappe-cli-state.json``
which belongs to the install wizard — the two never read each other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

BENCH_MARKERS = {"sites", "apps"}
FP_YAML = ".fp.yaml"


def find_bench_root(start: Path) -> Optional[Path]:
    """Walk up from *start* until a Frappe bench root is found.

    A bench root is any directory that contains both a ``sites/`` and an
    ``apps/`` subdirectory.  Returns ``None`` if no bench is found before
    the filesystem root.
    """
    for candidate in [start, *start.parents]:
        if all((candidate / marker).exists() for marker in BENCH_MARKERS):
            return candidate
    return None


def read_active_site(bench_root: Path) -> Optional[str]:
    """Return the active site name stored in ``.fp.yaml``, or ``None``."""
    fp = bench_root / FP_YAML
    if not fp.exists():
        return None
    try:
        data = yaml.safe_load(fp.read_text()) or {}
        return data.get("site") or None
    except Exception:
        return None


def write_active_site(bench_root: Path, site: str) -> None:
    """Write *site* as the active site into ``<bench_root>/.fp.yaml``."""
    fp = bench_root / FP_YAML
    fp.write_text(yaml.dump({"site": site}, default_flow_style=False))


def site_exists(bench_root: Path, site: str) -> bool:
    """Return True when *site* has a ``site_config.json`` in this bench."""
    return (bench_root / "sites" / site / "site_config.json").exists()


def list_sites(bench_root: Path) -> list[str]:
    """Return all site names found under ``<bench_root>/sites/``."""
    sites_dir = bench_root / "sites"
    if not sites_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in sites_dir.iterdir()
        if d.is_dir() and (d / "site_config.json").exists()
    )
