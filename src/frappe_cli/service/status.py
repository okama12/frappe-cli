import os

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..utils import shell
from ..utils.logging import get_logger

SERVICES = ["mariadb", "redis-server", "nginx", "supervisor"]

logger = get_logger("service.status")
console = Console()

# Helper to run shell commands and handle errors


class ShellRunner:
    def __init__(self, console, logger):
        self.console = console
        self.logger = logger

    def run(self, cmd, description=None, check=True):
        try:
            if hasattr(shell, "run"):
                result = shell.run(cmd)
            else:
                import subprocess

                result = subprocess.run(
                    cmd, check=check, capture_output=True, text=True
                )
                result = result.stdout
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
        bench_path = bench_name
        if not os.path.isabs(bench_path):
            # Try current directory first
            if not os.path.isdir(bench_path):
                # Try in home directory
                home_bench_path = os.path.expanduser(f"~/{bench_path}")
                if os.path.isdir(home_bench_path):
                    bench_path = home_bench_path
                    console.print(
                        f"[yellow]Bench directory not found in current directory, using: {bench_path}[/yellow]"
                    )
        if os.path.isdir(bench_path):
            console.print(f"[green]Bench directory:[/green] {bench_path} exists")
            sites_dir = os.path.join(bench_path, "sites")
            if site_name and os.path.isdir(os.path.join(sites_dir, site_name)):
                console.print(f"[green]Site:[/green] {site_name} exists")
                try:
                    apps = shell_runner.run(
                        ["bench", "list-apps", "--site", site_name],
                        description="List installed apps",
                        check=False,
                    )
                    if apps:
                        console.print("Installed apps:")
                        for app in apps.splitlines():
                            console.print(f"  - {app}")
                except Exception:
                    pass

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
    ssl_path = f"/etc/letsencrypt/live/{site_name}/fullchain.pem"
    try:
        ssl_exists = site_name and os.path.isfile(ssl_path)
    except PermissionError:
        ssl_exists = bool(site_name)  # root-owned path exists
    if ssl_exists:
        exp_date = shell_runner.run(
            ["openssl", "x509", "-enddate", "-noout", "-in", ssl_path],
            description="Check SSL expiry",
            check=False,
        )
        if exp_date and "=" in exp_date:
            exp = exp_date.split("=")[1].strip()
            console.print(f"[green]SSL certificate valid until:[/green] {exp}")
        else:
            console.print(
                f"[yellow]Could not determine SSL certificate expiry for {site_name}[/yellow]"
            )
    else:
        console.print(f"[red]SSL certificate not found for {site_name}[/red]")
    logger.info("[service] Status check completed.")
