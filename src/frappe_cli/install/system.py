import getpass
import logging
import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

LOG_FILE = (
    "/var/log/frappe-installer.log"
    if getpass.getuser() == "root"
    else "frappe-installer.log"
)
console = Console()


def setup_logger():
    logger = logging.getLogger("frappe_installer.install.system")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        try:
            handler = logging.FileHandler(LOG_FILE)
        except PermissionError:
            handler = logging.FileHandler("frappe-installer.log")
        formatter = logging.Formatter("[%(asctime)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger()


def print_system_info():
    table = Table(
        _title="System Information", show_header=True, _header_style="bold cyan"
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


class RichShell:
    def __init__(self, console, dry_run=False, debug=False):
        self.console = console
        self.dry_run = dry_run
        self.debug = debug

    def run(self, cmd, description, ignore_errors=False):
        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {' '.join(cmd)}[/dim]")
        if self.dry_run:
            self.console.print(f"[yellow][dry-run] {description}: {' '.join(cmd)}")
            logger.info(f"[dry-run] {description}: {' '.join(cmd)}")
            return

        self.console.print(f"[blue]{description}...[/blue]")
        try:
            result = subprocess.run(cmd, check=True)
            logger.info(f"[system] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            return result

        except subprocess.CalledProcessError:
            logger.error(f"[system] Failed: {' '.join(cmd)}")
            self.console.print(f"[bold red]✗ {description} failed.[/bold red]")
            if not ignore_errors:
                sys.exit(1)
            else:
                self.console.print("[yellow]Continuing despite error...[/yellow]")


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
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
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
