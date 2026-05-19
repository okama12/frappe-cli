"""Shared helpers to detect Let's Encrypt certificates for a site.

`/etc/letsencrypt/live/` is mode 700 and owned by root, so a plain
`Path.exists()` often returns False or raises `PermissionError` on
Python 3.12. Bench leaves readable breadcrumbs we can check without sudo;
when those are inconclusive, callers may pass a sudo password.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def cert_path(site_name: str) -> str:
    return f"/etc/letsencrypt/live/{site_name}/fullchain.pem"


def cert_exists(
    site_name: str,
    sudo_password: str = "",
    bench_path: str | Path | None = None,
) -> bool:
    """Return True if an SSL certificate appears to exist for `site_name`."""
    path = cert_path(site_name)

    try:
        if Path(path).exists():
            return True
    except (PermissionError, OSError):
        pass

    if _bench_letsencrypt_config_exists(site_name):
        return True

    if bench_path and _bench_nginx_has_ssl(site_name, Path(bench_path)):
        return True

    if sudo_password:
        return _sudo_test_f(path, sudo_password)

    # Passwordless sudo (NOPASSWD) — fast path when configured.
    return _sudo_test_f_non_interactive(path)


def _bench_letsencrypt_config_exists(site_name: str) -> bool:
    """Bench writes a world-readable certbot config per site after lets-encrypt."""
    cfg = Path(f"/etc/letsencrypt/configs/{site_name}.cfg")
    if not cfg.is_file():
        return False
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return site_name in text or "domains" in text


def _bench_nginx_has_ssl(site_name: str, bench_path: Path) -> bool:
    """True when the bench nginx config references this site's live cert."""
    nginx_conf = bench_path / "config" / "nginx.conf"
    if not nginx_conf.is_file():
        return False
    needle = f"/etc/letsencrypt/live/{site_name}/"
    try:
        return needle in nginx_conf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _sudo_test_f(path: str, password: str) -> bool:
    try:
        proc = subprocess.run(
            ["sudo", "-S", "test", "-f", path],
            input=(password + "\n").encode(),
            capture_output=True,
            timeout=15,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _sudo_test_f_non_interactive(path: str) -> bool:
    try:
        proc = subprocess.run(
            ["sudo", "-n", "test", "-f", path],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def cert_expiry(site_name: str, sudo_password: str = "") -> str:
    """Return openssl's notAfter string, or '' if unavailable."""
    path = cert_path(site_name)
    for cmd, inp in _openssl_cmds(path, sudo_password):
        try:
            proc = subprocess.run(
                cmd,
                input=inp,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0 and "=" in proc.stdout:
                return proc.stdout.split("=", 1)[1].strip()
        except (OSError, subprocess.TimeoutExpired):
            continue
    return ""


def _openssl_cmds(path: str, sudo_password: str):
    base = ["openssl", "x509", "-enddate", "-noout", "-in", path]
    yield base, None
    if sudo_password:
        yield ["sudo", "-S"] + base, (sudo_password + "\n").encode()
    yield ["sudo", "-n"] + base, None
