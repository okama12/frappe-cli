from typing import Callable

from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..install.context import InstallContext
from ..install.state import InstallState
from ..utils.errors import ValidationError
from ..utils.git_repo import is_official_frappe_app, resolve_app_branch
from ..utils.validators import (
    validate_bench_name,
    validate_branch_name,
    validate_email,
    validate_git_url,
    validate_site_name,
)
from .panels import print_header


def _ask_validated(
    console: Console,
    label: str,
    validator: Callable[[str], str],
    *,
    default: str | None = None,
    allow_empty: bool = False,
) -> str:
    """Prompt repeatedly until *validator* accepts the input."""
    while True:
        if default is None:
            value = Prompt.ask(label)
        else:
            value = Prompt.ask(label, default=default)
        if allow_empty and not value:
            return ""
        try:
            return validator(value)
        except ValidationError as exc:
            console.print(f"  [red]{exc}[/red]")


def _detect_ubuntu_version() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    return line.split("=")[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return "22.04"


def _resolve_branch_for_prompt(
    console: Console, app_url: str, frappe_branch: str
) -> str:
    """Ask for the app branch, using smart defaults depending on app type."""
    if not app_url:
        return frappe_branch

    if is_official_frappe_app(app_url):
        # Official apps (erpnext, hrms, …) are versioned the same as Frappe.
        return _ask_validated(
            console,
            "  App branch",
            validate_branch_name,
            default=frappe_branch,
        )

    # Custom / third-party app: try remote branch detection.
    console.print("  [dim]Detecting remote branches…[/dim]", end="")
    branch, hint = resolve_app_branch(app_url, frappe_branch)
    console.print("\r" + " " * 35 + "\r", end="")  # clear the line

    if hint:
        console.print(f"\n  [yellow]{hint}[/yellow]\n")
    else:
        console.print(
            f"  [dim]Remote branches found. "
            f"Suggested branch: [bold]{branch}[/bold][/dim]"
        )

    return _ask_validated(console, "  App branch", validate_branch_name, default=branch)


def _prompt_mariadb_password(console: Console) -> str:
    """Ask for MariaDB root password twice and loop until entries match."""
    while True:
        password = Prompt.ask(
            "  MariaDB root password (stored for this server — verify carefully)",
            password=True,
        )
        confirm = Prompt.ask("  Confirm MariaDB root password", password=True)
        if password == confirm:
            return password
        console.print("  [red]Passwords do not match. Please try again.[/red]\n")


def collect_inputs(
    console: Console, dry_run: bool = False, debug: bool = False, skip_ssl: bool = False
) -> InstallContext:
    print_header(console)
    console.print("\n  Let's get your Frappe production server ready.\n")

    console.print("  [bold]── Server Configuration ──[/bold]")
    bench_name = _ask_validated(
        console, "  Bench name", validate_bench_name, default="frappe-bench"
    )
    site_name = _ask_validated(console, "  Site name (FQDN)", validate_site_name)
    frappe_branch = _ask_validated(
        console, "  Frappe branch", validate_branch_name, default="version-15"
    )

    console.print("\n  [bold]── App ──[/bold]")
    app_url = _ask_validated(
        console,
        "  App GitHub URL (leave blank for Frappe only)",
        validate_git_url,
        default="",
        allow_empty=True,
    )
    app_branch = _resolve_branch_for_prompt(console, app_url, frappe_branch)

    console.print("\n  [bold]── Credentials ──[/bold]")
    sudo_password = Prompt.ask("  Sudo password", password=True)
    mariadb_root_password = _prompt_mariadb_password(console)
    admin_password = Prompt.ask("  Frappe site admin password", password=True)
    ssl_email = (
        _ask_validated(console, "  SSL email (Let's Encrypt)", validate_email)
        if not skip_ssl
        else ""
    )

    console.print("\n  [bold]── Daily Developer Workflow ──[/bold]")
    enable_passwordless_restart = Confirm.ask(
        "  Allow passwordless 'fp restart' for this user?\n"
        "  [dim](adds a sudoers rule so bench restart never prompts for a password)[/dim]",
        default=True,
    )

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
        enable_passwordless_restart=enable_passwordless_restart,
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

    done = set(state.completed_steps)

    console.print("  [bold]── Re-enter credentials ──[/bold]")

    # sudo is always needed — remaining steps (production, SSL, restart) all use it
    sudo_password = Prompt.ask("  Sudo password", password=True)

    # Needed for MariaDB setup steps AND for site creation (piped to bench new-site stdin).
    needs_mariadb = "mariadb_secure" not in done or "site_create" not in done
    mariadb_root_password = _prompt_mariadb_password(console) if needs_mariadb else ""

    # Only needed if the site hasn't been created yet
    admin_password = (
        ""
        if "site_create" in done
        else Prompt.ask("  Frappe site admin password", password=True)
    )

    if "sudoers_setup" not in done:
        console.print("\n  [bold]── Daily Developer Workflow ──[/bold]")
        enable_passwordless_restart = Confirm.ask(
            "  Allow passwordless 'fp restart' for this user?\n"
            "  [dim](adds a sudoers rule so bench restart never prompts for a password)[/dim]",
            default=state.enable_passwordless_restart or True,
        )
    else:
        enable_passwordless_restart = state.enable_passwordless_restart

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
        enable_passwordless_restart=enable_passwordless_restart,
    )
