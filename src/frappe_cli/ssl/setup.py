"""`fcli ssl setup` — install a Let's Encrypt certificate for an existing site.

Uses `bench setup lets-encrypt <site>` (NOT raw `certbot --nginx`) so that
bench rewrites this bench's nginx config with the SSL block and registers the
monthly renewal cron — same flow as the manual runbook in
`docs/superpowers/test3-bench-setup.md` and the install wizard's SSLSetupStep.

Works for any site already created under any bench in `$HOME` (auto-detects
the bench by scanning `~/<bench>/sites/<site>/site_config.json`).
"""

import getpass
import os
import subprocess
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger("ssl.setup")


def _find_bench_for_site(site_name: str, bench_name: str = "") -> Path:
    """Return the bench path that contains <site>/site_config.json.

    If `bench_name` is given, only check that bench. Otherwise scan all
    immediate subdirectories of `$HOME` for the first match.
    """
    home = Path.home()
    candidates: list[Path] = []
    if bench_name:
        candidates = [home / bench_name]
    else:
        try:
            candidates = sorted(p for p in home.iterdir() if p.is_dir())
        except OSError:
            candidates = []

    for bench_path in candidates:
        site_config = bench_path / "sites" / site_name / "site_config.json"
        if site_config.exists():
            return bench_path

    if bench_name:
        raise click.ClickException(
            f"Site {site_name} not found under {home / bench_name}/sites/"
        )
    raise click.ClickException(
        f"No bench under {home} contains site {site_name}. "
        f"Use --bench-name to specify it explicitly."
    )


def _local_bin_path() -> str:
    """Ensure ~/.local/bin (where uv installs `bench`) is on PATH for sudo."""
    local_bin = str(Path.home() / ".local" / "bin")
    current = os.environ.get("PATH", "")
    parts = current.split(":")
    if local_bin not in parts:
        return f"{local_bin}:{current}" if current else local_bin
    return current


def _cert_exists(site_name: str, sudo_password: str) -> bool:
    """`/etc/letsencrypt/live/` is root-owned 700, so non-root stat raises
    PermissionError on Python 3.12. Use `sudo test -f` for an authoritative
    answer (same trick as `SSLSetupStep.check`)."""
    cert_path = f"/etc/letsencrypt/live/{site_name}/fullchain.pem"
    try:
        return Path(cert_path).exists()
    except (PermissionError, OSError):
        pass
    try:
        proc = subprocess.run(
            ["sudo", "-S", "test", "-f", cert_path],
            input=(sudo_password + "\n").encode(),
            capture_output=True,
            timeout=15,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _register_letsencrypt(email: str, sudo_password: str) -> None:
    """Register an ACME account if not already registered. Idempotent — exits
    cleanly when an account already exists for the chosen ACME server."""
    try:
        subprocess.run(
            [
                "sudo",
                "-S",
                "certbot",
                "register",
                "-m",
                email,
                "--agree-tos",
                "--no-eff-email",
                "--non-interactive",
            ],
            input=(sudo_password + "\n").encode(),
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        # Don't fail outright; if registration is actually missing, the
        # subsequent `bench setup lets-encrypt` will error and report it.
        logger.debug(f"certbot register call failed (will retry inline): {e}")


@click.command()
@click.option(
    "--site-name",
    prompt="Site (FQDN)",
    help="The site (FQDN) to issue an SSL certificate for, e.g. test5.rashidiokama.com",
)
@click.option(
    "--bench-name",
    default="",
    show_default=False,
    help="Bench directory name (omit to auto-detect from $HOME/*/sites/<site>)",
)
@click.option(
    "--email",
    default="",
    show_default=False,
    help="Let's Encrypt account email (required only the first time on a host)",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-run `bench setup lets-encrypt` even when a cert already exists",
)
def setup(site_name: str, bench_name: str, email: str, force: bool) -> None:
    """Issue or renew a Let's Encrypt SSL certificate for an existing site.

    Wraps `sudo -H env "PATH=$PATH" bench setup lets-encrypt <site>` so the
    bench's own nginx config is updated and the monthly renewal cron is set,
    matching the proven manual runbook.

    Examples:
        fcli ssl setup --site-name test5.rashidiokama.com
        fcli ssl setup --site-name site.example.com --bench-name my-bench
        fcli ssl setup --site-name site.example.com --email me@example.com
    """
    logger.info(f"[ssl] Setting up SSL for {site_name}")
    bench_path = _find_bench_for_site(site_name, bench_name)
    console.print(f"[cyan]Bench:[/cyan] {bench_path}")
    console.print(f"[cyan]Site:[/cyan]  {site_name}")

    sudo_password = getpass.getpass("Sudo password: ")

    if _cert_exists(site_name, sudo_password) and not force:
        console.print(
            f"[yellow]Certificate already exists for {site_name}. "
            f"Use --force to re-run anyway.[/yellow]"
        )
        return

    if email:
        console.print(f"[cyan]Registering ACME account ({email}) if needed...[/cyan]")
        _register_letsencrypt(email, sudo_password)

    bench_bin = str(Path.home() / ".local" / "bin" / "bench")
    path_env = _local_bin_path()

    console.print(f"[cyan]Running:[/cyan] sudo -H bench setup lets-encrypt {site_name}")
    # bench prompts twice: stop nginx? y, overwrite nginx.conf? y
    proc = subprocess.run(
        [
            "sudo",
            "-S",
            "-H",
            "env",
            f"PATH={path_env}",
            bench_bin,
            "setup",
            "lets-encrypt",
            site_name,
        ],
        input=(sudo_password + "\ny\ny\n").encode(),
        cwd=str(bench_path),
    )
    if proc.returncode != 0:
        raise click.ClickException(
            "bench setup lets-encrypt failed. Inspect /var/log/letsencrypt/letsencrypt.log "
            "or run the command manually:\n"
            f'  cd {bench_path} && sudo -H env "PATH=$PATH" '
            f"bench setup lets-encrypt {site_name}"
        )

    if not _cert_exists(site_name, sudo_password):
        raise click.ClickException(
            f"bench finished but no certificate file at "
            f"/etc/letsencrypt/live/{site_name}/fullchain.pem"
        )

    logger.info(f"[ssl] SSL/HTTPS set up for {site_name}")
    console.print(
        f"[green]✓ SSL/HTTPS set up for {site_name}. "
        f"Auto-renewal cron installed by bench.[/green]"
    )
    console.print(f"  Try: [bold]curl -I https://{site_name}[/bold]")


# Keep helper exposed for tests
_find_bench_for_site_for_tests: Optional[callable] = _find_bench_for_site  # type: ignore
