"""`frappe ssl list` — list every site across every bench and whether each
has a Let's Encrypt certificate. Useful for finding sites that still need SSL.

Sites are discovered by scanning `$HOME/<bench>/sites/<site>/site_config.json`,
so it works for any layout produced by `bench init`.
"""

import getpass
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..utils.logging import get_logger

console = Console()
logger = get_logger("ssl.list")


def _discover_sites() -> list[tuple[str, str]]:
    """Return [(bench_name, site_name), ...] for every site under $HOME."""
    home = Path.home()
    pairs: list[tuple[str, str]] = []
    try:
        for bench_dir in sorted(home.iterdir()):
            if not bench_dir.is_dir():
                continue
            sites_dir = bench_dir / "sites"
            if not sites_dir.is_dir():
                continue
            for site in sorted(sites_dir.iterdir()):
                if not site.is_dir():
                    continue
                if (site / "site_config.json").exists():
                    pairs.append((bench_dir.name, site.name))
    except OSError:
        pass
    return pairs


def _has_cert(site_name: str, sudo_password: str = "") -> bool | None:
    """True if cert file exists, False if not, None if we can't tell.

    /etc/letsencrypt/live/ is mode 700 root-owned, so we may need sudo to
    stat it. If no sudo password is provided we try without sudo first;
    on PermissionError we return None so the caller shows "?" not "No".
    """
    cert_path = f"/etc/letsencrypt/live/{site_name}/fullchain.pem"
    try:
        return Path(cert_path).exists()
    except (PermissionError, OSError):
        pass
    if not sudo_password:
        return None
    try:
        proc = subprocess.run(
            ["sudo", "-S", "test", "-f", cert_path],
            input=(sudo_password + "\n").encode(),
            capture_output=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None


@click.command("list")
@click.option(
    "--sudo/--no-sudo",
    "use_sudo",
    default=True,
    help="Prompt for sudo password to authoritatively stat /etc/letsencrypt/live/",
)
def list_certs(use_sudo: bool) -> None:
    """List sites and their SSL status across every bench under $HOME."""
    pairs = _discover_sites()
    if not pairs:
        console.print(
            f"[yellow]No benches with sites found under {Path.home()}[/yellow]"
        )
        return

    sudo_password = ""
    if use_sudo:
        try:
            sudo_password = getpass.getpass(
                "Sudo password (blank to skip authoritative check): "
            )
        except (EOFError, KeyboardInterrupt):
            sudo_password = ""

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Bench")
    table.add_column("Site")
    table.add_column("HTTPS")
    table.add_column("Hint")

    missing: list[str] = []
    for bench_name, site_name in pairs:
        has = _has_cert(site_name, sudo_password)
        if has is True:
            cell = "[green]Yes[/green]"
            hint = ""
        elif has is False:
            cell = "[red]No[/red]"
            hint = f"fcli ssl setup --site-name {site_name}"
            missing.append(site_name)
        else:
            cell = "[yellow]?[/yellow]"
            hint = "re-run with sudo"
        table.add_row(bench_name, site_name, cell, hint)

    console.print(table)
    if missing:
        console.print(
            f"\n[yellow]{len(missing)} site(s) without SSL.[/yellow] "
            "Run `fcli ssl setup --site-name <site>` for each."
        )
