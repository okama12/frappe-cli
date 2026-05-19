import os
import subprocess

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..utils import shell
from ..utils.logging import get_logger
from ..utils.ssl_cert import cert_exists, cert_expiry

SERVICES = ["mariadb", "redis-server", "nginx", "supervisor"]

logger = get_logger("service.status")
console = Console()

# Helper to run shell commands and handle errors


class ShellRunner:
    def __init__(self, console, logger):
        self.console = console
        self.logger = logger

    def run(self, cmd, description=None, check=True, cwd=None):
        try:
            if hasattr(shell, "run"):
                result = shell.run(cmd, check=check, cwd=cwd)
            else:
                proc = subprocess.run(
                    cmd,
                    check=check,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                )
                result = proc.stdout
            if result is None:
                if description:
                    self.console.print(
                        f"[yellow]Warning: {description} returned no output[/yellow]"
                    )
                return ""

            return result

        except Exception as e:
            msg = f"[red]Error running {' '.join(cmd)}: {str(e)}[/red]"
            self.console.print(msg)
            self.logger.error(msg)
            if check:
                raise click.ClickException(f"Command failed: {str(e)}")
            return ""


shell_runner = ShellRunner(console, logger)


def _resolve_bench_path(bench_name: str) -> str | None:
    """Return an absolute bench path if the directory exists."""
    bench_path = bench_name
    if os.path.isabs(bench_path):
        return bench_path if os.path.isdir(bench_path) else None
    if os.path.isdir(bench_path):
        return os.path.abspath(bench_path)
    home_bench = os.path.expanduser(f"~/{bench_path}")
    return home_bench if os.path.isdir(home_bench) else None


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option(
    "--site-name",
    prompt="Enter site name",
    default="",
    show_default=False,
    help="Frappe site name (optional)",
)
def status(bench_name, site_name):
    """Show system, service, and Frappe/Bench status with rich output."""
    logger.info("[service] Checking system status...")
    console.print(
        Panel.fit("[bold blue]System Information[/bold blue]", border_style="blue")
    )
    # Hostname
    console.print(f"[cyan]Hostname:[/cyan] {os.uname().nodename}")
    # OS
    os_release = shell_runner.run(
        ["cat", "/etc/os-release"], description="Get OS release info", check=False
    )
    os_name = "Unknown"
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME"):
            os_name = line.split("=")[1].strip().strip('"')
            break
    console.print(f"[cyan]OS:[/cyan] {os_name}")
    # Kernel
    console.print(f"[cyan]Kernel:[/cyan] {os.uname().release}")
    # Memory
    mem = shell_runner.run(["free", "-h"], description="Get memory info", check=False)
    mem_str = "Unknown"
    for line in mem.splitlines():
        if line.startswith("Mem"):
            parts = line.split()
            if len(parts) >= 4:
                mem_str = f"{parts[2]}/{parts[1]} used"
            break
    console.print(f"[cyan]Memory:[/cyan] {mem_str}")
    # Disk
    disk = shell_runner.run(["df", "-h", "/"], description="Get disk info", check=False)
    disk_str = "Unknown"
    for line in disk.splitlines()[1:2]:
        parts = line.split()
        if len(parts) >= 5:
            disk_str = f"{parts[2]}/{parts[1]} ({parts[4]} used)"
    console.print(f"[cyan]Disk:[/cyan] {disk_str}")
    console.print()

    # Service Status
    console.print(
        Panel.fit("[bold blue]Service Status[/bold blue]", border_style="blue")
    )
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Service")
    table.add_column("Status")
    for service in SERVICES:
        status = shell_runner.run(
            ["systemctl", "is-active", service],
            description=f"Check {service} status",
            check=False,
        )
        if status.strip() == "active":
            table.add_row(service, "[green]Running[/green]")
        else:
            table.add_row(service, "[red]Stopped[/red]")
    console.print(table)
    console.print()

    # Frappe/Bench Status
    console.print(
        Panel.fit("[bold blue]Frappe/Bench Status[/bold blue]", border_style="blue")
    )
    bench_cli = shell_runner.run(
        ["which", "bench"], description="Check Bench CLI", check=False
    )
    if bench_cli.strip():
        version = shell_runner.run(
            ["bench", "--version"], description="Get Bench version", check=False
        )
        console.print(f"[green]Bench CLI:[/green] {version.strip()}")
        bench_path = _resolve_bench_path(bench_name)
        if (
            bench_path
            and not os.path.isdir(bench_name)
            and not os.path.isabs(bench_name)
        ):
            console.print(
                f"[yellow]Bench directory not found in current directory, using: {bench_path}[/yellow]"
            )
        if bench_path and os.path.isdir(bench_path):
            console.print(f"[green]Bench directory:[/green] {bench_path} exists")
            sites_dir = os.path.join(bench_path, "sites")
            if site_name and os.path.isdir(os.path.join(sites_dir, site_name)):
                console.print(f"[green]Site:[/green] {site_name} exists")
                # bench only accepts `--site` when cwd is inside the bench tree.
                apps = shell_runner.run(
                    ["bench", "--site", site_name, "list-apps"],
                    description="List installed apps",
                    check=False,
                    cwd=bench_path,
                )
                if apps.strip():
                    console.print("Installed apps:")
                    for app in apps.splitlines():
                        if app.strip():
                            console.print(f"  - {app.strip()}")
                else:
                    console.print(
                        "[yellow]Could not list installed apps "
                        f"(run from {bench_path}: "
                        f"bench --site {site_name} list-apps)[/yellow]"
                    )

            elif site_name:
                console.print(f"[red]Site: {site_name} not found[/red]")
        else:
            console.print(f"[red]Bench directory: {bench_name} not found[/red]")
    else:
        console.print("[red]Bench CLI: Not installed[/red]")
    console.print()

    # SSL Certificate
    console.print(
        Panel.fit("[bold blue]SSL Certificate[/bold blue]", border_style="blue")
    )
    if not site_name:
        console.print("[yellow]No site name provided — skipping SSL check[/yellow]")
    else:
        resolved_bench = _resolve_bench_path(bench_name)
        has_ssl = cert_exists(
            site_name,
            bench_path=resolved_bench,
        )
        if has_ssl:
            exp = cert_expiry(site_name)
            if exp:
                console.print(f"[green]SSL certificate valid until:[/green] {exp}")
            else:
                console.print(
                    f"[green]SSL configured for {site_name}[/green] "
                    "(Let's Encrypt / bench nginx)"
                )
                console.print(
                    "[dim]  Expiry date needs sudo to read the cert file — "
                    "run: sudo openssl x509 -enddate -noout -in "
                    f"/etc/letsencrypt/live/{site_name}/fullchain.pem[/dim]"
                )
        else:
            console.print(f"[red]SSL certificate not found for {site_name}[/red]")
            console.print(
                "[dim]  If you just installed SSL, try: "
                f"frappe ssl setup --site-name {site_name}[/dim]"
            )
    logger.info("[service] Status check completed.")
