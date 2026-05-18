import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("install.system")


def print_system_info():
    table = Table(
        title="System Information", show_header=True, header_style="bold cyan"
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    import platform

    table.add_row("OS", platform.system())
    table.add_row("OS Release", platform.release())
    table.add_row("OS Version", platform.version())
    table.add_row("Machine", platform.machine())
    table.add_row("Python Version", platform.python_version())
    table.add_row("Architecture", platform.architecture()[0])
    if platform.system() == "Linux":
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("_PRETTY_NAME ="):
                        distro = line.split("=")[1].strip().strip('"')
                        table.add_row("Distribution", distro)
                        break
        except FileNotFoundError:
            table.add_row("Distribution", "Unknown")
    console.print(table)
    console.print()


def validate_sudo():
    console.print("[yellow]Validating sudo access[/yellow]")
    try:
        subprocess.run(["sudo", "-v"], check=True)
        console.print("[bold green]✓ Sudo privileges validated[/bold green]")
    except subprocess.CalledProcessError:
        console.print(
            "[bold red]✗ Sudo validation failed. Please ensure you have sudo privileges.[/bold red]"
        )
        sys.exit(1)


def detect_package_manager():
    if subprocess.call(["which", "apt"], stdout=subprocess.DEVNULL) == 0:
        return "apt"

    elif subprocess.call(["which", "dnf"], stdout=subprocess.DEVNULL) == 0:
        return "dnf"

    elif subprocess.call(["which", "yum"], stdout=subprocess.DEVNULL) == 0:
        return "yum"

    else:
        console.print("[bold red]Unsupported package manager. Supported: apt, dnf, yum")
        sys.exit(1)


@click.command()
@click.option("--dry-run", is_flag=True, help="Print commands without executing them")
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
@click.pass_context
def system(ctx, dry_run, debug, ignore_errors):
    """Update system, install essential packages."""
    _ = ctx.obj.get("CONFIG", {})
    print_system_info()
    validate_sudo()
    pkg_mgr = detect_package_manager()
    logger.info(f"[system] Detected package manager: {pkg_mgr}")
    logger.info("[system] Starting system update and setup...")
    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="install.system"
    )
    if pkg_mgr == "apt":
        shell_runner.run(
            ["sudo", "apt", "update"],
            "Updating package lists",
            ignore_errors=ignore_errors,
        )
        shell_runner.run(
            ["sudo", "_DEBIAN_FRONTEND =noninteractive", "apt", "upgrade", "-y"],
            "Upgrading packages",
            ignore_errors=ignore_errors,
        )
        shell_runner.run(
            [
                "sudo",
                "apt",
                "install",
                "-y",
                "curl",
                "wget",
                "git",
                "software-properties-common",
                "apt-transport-https",
                "ca-certificates",
            ],
            "Installing essential packages",
            ignore_errors=ignore_errors,
        )
    elif pkg_mgr in ["dnf", "yum"]:
        shell_runner.run(
            ["sudo", pkg_mgr, "makecache"],
            "Updating package lists",
            ignore_errors=ignore_errors,
        )
        shell_runner.run(
            ["sudo", pkg_mgr, "upgrade", "-y"],
            "Upgrading packages",
            ignore_errors=ignore_errors,
        )
        shell_runner.run(
            [
                "sudo",
                pkg_mgr,
                "install",
                "-y",
                "curl",
                "wget",
                "git",
                "ca-certificates",
            ],
            "Installing essential packages",
            ignore_errors=ignore_errors,
        )
    logger.info("[system] System update and setup complete.")
    console.print("[bold green]System update and essentials installed successfully!")
