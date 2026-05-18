from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..install.context import InstallContext
from ..install.state import InstallState
from .panels import print_header


def _detect_ubuntu_version() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    return line.split("=")[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return "22.04"


def collect_inputs(
    console: Console, dry_run: bool = False, debug: bool = False, skip_ssl: bool = False
) -> InstallContext:
    print_header(console)
    console.print("\n  Let's get your Frappe production server ready.\n")

    console.print("  [bold]── Server Configuration ──[/bold]")
    bench_name = Prompt.ask("  Bench name", default="frappe-bench")
    site_name = Prompt.ask("  Site name (FQDN)")
    frappe_branch = Prompt.ask("  Frappe branch", default="version-15")

    console.print("\n  [bold]── App ──[/bold]")
    app_url = Prompt.ask("  App GitHub URL")
    app_branch = Prompt.ask("  App branch", default=frappe_branch)

    console.print("\n  [bold]── Credentials ──[/bold]")
    sudo_password = Prompt.ask("  Sudo (VPS admin) password", password=True)
    mariadb_root_password = Prompt.ask(
        "  MariaDB root password (will be set)", password=True
    )
    admin_password = Prompt.ask("  Frappe site admin password", password=True)
    ssl_email = Prompt.ask("  SSL email (Let's Encrypt)")

    ubuntu_version = _detect_ubuntu_version()
    console.print(f"\n  [dim]Detected Ubuntu {ubuntu_version}[/dim]\n")

    if not Confirm.ask("  Ready to install (10–20 min). Continue?", default=True):
        raise SystemExit(0)

    return InstallContext(
        bench_name=bench_name,
        site_name=site_name,
        frappe_branch=frappe_branch,
        app_url=app_url,
        app_branch=app_branch,
        sudo_password=sudo_password,
        mariadb_root_password=mariadb_root_password,
        admin_password=admin_password,
        ssl_email=ssl_email,
        ubuntu_version=ubuntu_version,
        dry_run=dry_run,
        debug=debug,
        skip_ssl=skip_ssl,
    )


def collect_credentials_for_resume(
    console: Console,
    state: InstallState,
    skip_ssl: bool = False,
    dry_run: bool = False,
    debug: bool = False,
) -> InstallContext:
    console.print("\n  [yellow]Resuming previous install.[/yellow]")
    console.print(
        f"  Site: [cyan]{state.site_name}[/cyan]  Bench: [cyan]{state.bench_name}[/cyan]\n"
    )

    console.print("  [bold]── Re-enter credentials ──[/bold]")
    sudo_password = Prompt.ask("  Sudo (VPS admin) password", password=True)
    mariadb_root_password = Prompt.ask("  MariaDB root password", password=True)
    admin_password = Prompt.ask("  Frappe site admin password", password=True)

    return InstallContext(
        bench_name=state.bench_name,
        site_name=state.site_name,
        frappe_branch=state.frappe_branch,
        app_url=state.app_url,
        app_branch=state.app_branch,
        sudo_password=sudo_password,
        mariadb_root_password=mariadb_root_password,
        admin_password=admin_password,
        ssl_email=state.ssl_email,
        ubuntu_version=state.ubuntu_version,
        dry_run=dry_run,
        debug=debug,
        skip_ssl=skip_ssl,
    )
