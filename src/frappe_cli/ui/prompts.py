"""Guided configuration and plan review shared by both setup entry points."""

import os
from pathlib import Path
from typing import Callable

import click
from rich.console import Console

from ..dev.context import discover_benches, find_bench_root, frappe_branch
from ..install.context import InstallContext
from ..install.plan import resolve_steps
from ..install.state import InstallState
from ..install.steps import ALL_STEPS
from ..utils.errors import ValidationError
from ..utils.git_repo import is_official_frappe_app, resolve_app_branch
from ..utils.validators import (
    validate_bench_name,
    validate_branch_name,
    validate_email,
    validate_git_url,
    validate_site_name,
)
from . import terminal
from .panels import print_header, print_plan

BENCH_STEPS = {
    "bench_init",
    "site_create",
    "app_get",
    "dns_multitenant",
    "production_setup",
    "sudoers_setup",
    "app_install",
    "bench_restart",
    "ssl_setup",
}
SITE_STEPS = {"site_create", "app_install", "ssl_setup"}
NO_SUDO = {
    "uv_check",
    "bench_install",
    "bench_init",
    "site_create",
    "app_get",
    "app_install",
    "dns_multitenant",
}


def _ask_validated(
    console: Console,
    label: str,
    validator: Callable[[str], str],
    *,
    default=None,
    allow_empty=False,
) -> str:
    while True:
        value = terminal.ask(console, label, default=default)
        if allow_empty and not value:
            return ""
        try:
            return validator(value)
        except ValidationError as exc:
            console.print(str(exc), style="red", markup=False)


def _detect_ubuntu_version() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("VERSION_ID="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return "unknown"


def _resolve_branch_for_prompt(console, app_url, frappe_branch, *, detect=True):
    if not app_url:
        return frappe_branch
    default = frappe_branch
    if not is_official_frappe_app(app_url):
        default = "main"
        if detect:
            default, hint = resolve_app_branch(app_url, frappe_branch)
            if hint:
                console.print(hint, style="yellow", markup=False)
    return _ask_validated(console, "App branch", validate_branch_name, default=default)


def _prompt_mariadb_password(console):
    if os.environ.get("FP_MARIADB_PASSWORD"):
        return os.environ["FP_MARIADB_PASSWORD"]
    while True:
        password = terminal.ask(console, "MariaDB root password", password=True)
        confirm = terminal.ask(console, "Confirm MariaDB root password", password=True)
        if password and password == confirm:
            return password
        console.print("Passwords must be non-empty and match. Try again.", style="red")


def _existing_directory(value):
    try:
        path = Path(value).expanduser().resolve(strict=True)
        if not value.strip() or not path.is_dir():
            raise ValueError("Not a directory")
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValidationError("Choose an existing directory on this server.") from exc
    return path


def _parent_directory(value):
    path = _existing_directory(value)
    if not os.access(path, os.W_OK | os.X_OK):
        raise ValidationError("The current user needs write access to this directory.")
    return str(path)


def _choose_parent_directory(console, default):
    """Browse the host filesystem without creating or changing directories."""
    try:
        current = _existing_directory(default)
    except ValidationError:
        console.print(
            "Previous directory is unavailable; starting at home.", style="yellow"
        )
        current = Path.home().resolve()
    while True:
        console.print("\nServer directory", style="bold")
        console.print(str(current), style="cyan", markup=False)
        choices = [("use", "Use this directory")]
        if current.parent != current:
            choices.append(("up", "../  Go to parent directory"))
        choices.append(("path", "Enter a path… (Tab completion)"))
        try:
            children = sorted(current.iterdir(), key=lambda path: path.name.casefold())
            for child in children:
                try:
                    if child.is_dir():
                        choices.append((str(child), f"{child.name}/"))
                except OSError:
                    continue
        except OSError:
            console.print(
                "Cannot list this directory. Go up or enter another path.",
                style="yellow",
            )
        choice = terminal.choose("Bench parent directory", choices)
        try:
            if choice == "use":
                return _parent_directory(str(current))
            if choice == "up":
                current = current.parent
            elif choice == "path":
                value = terminal.ask_directory(console, default=str(current) + os.sep)
                target = Path(value).expanduser()
                if not target.is_absolute():
                    target = current / target
                current = _existing_directory(str(target) if value.strip() else "")
            else:
                current = _existing_directory(choice)
        except ValidationError as exc:
            console.print(str(exc), style="red", markup=False)


def _existing_branch(name, parent):
    return frappe_branch(Path(parent) / name) or "version-15"


def _bench_inputs(console, previous):
    current = find_bench_root(Path.cwd())
    default_name = previous.get(
        "bench_name", current.name if current else "frappe-bench"
    )
    default_parent = previous.get(
        "bench_parent", str(current.parent if current else Path.home())
    )
    if terminal.interactive():
        choices = [(str(path), f"Use {path}") for path in discover_benches()]
        choices.append(("new", "New bench: browse server directories"))
        choice = terminal.choose("Bench", choices)
        if choice != "new":
            path = Path(choice)
            return path.name, str(path.parent)
        parent = _choose_parent_directory(console, default_parent)
    else:
        parent = _ask_validated(
            console, "Parent directory", _parent_directory, default=default_parent
        )
    name = _ask_validated(
        console, "Bench name", validate_bench_name, default=default_name
    )
    console.print(f"Bench location: {Path(parent) / name}", style="dim", markup=False)
    return name, parent


def collect_inputs(
    console: Console, dry_run=False, debug=False, skip_ssl=False, components=None
) -> InstallContext:
    print_header(console)
    selected = [step.name for step in ALL_STEPS]
    workflow = "production"
    if components is not None:
        workflow = "custom"
        requested = components or terminal.choose(
            "Choose components (dependencies are included automatically)",
            [(step.name, step.description) for step in ALL_STEPS],
            multiple=True,
        )
        selected = resolve_steps(requested)
        added = set(selected) - set(requested)
        if added:
            console.print(
                "Required dependencies added: " + ", ".join(sorted(added)),
                style="dim",
                markup=False,
            )
    if skip_ssl and "ssl_setup" in selected:
        selected.remove("ssl_setup")
    chosen = set(selected)
    previous: dict[str, str] = {}
    while True:
        console.print(
            "\n[bold]Configuration[/bold]  [dim]Ctrl+C cancels before installation[/dim]"
        )
        bench_name, bench_parent = (
            _bench_inputs(console, previous) if chosen & BENCH_STEPS else ("", "")
        )
        site_name = (
            _ask_validated(
                console,
                "Site domain",
                validate_site_name,
                default=previous.get("site_name"),
            )
            if chosen & SITE_STEPS
            else ""
        )
        frappe_branch = (
            _ask_validated(
                console,
                "Frappe branch",
                validate_branch_name,
                default=previous.get(
                    "frappe_branch", _existing_branch(bench_name, bench_parent)
                ),
            )
            if "bench_init" in chosen
            else "version-15"
        )
        app_url = (
            _ask_validated(
                console,
                "App name or repository (blank for Frappe only)",
                validate_git_url,
                default=previous.get("app_url", ""),
                allow_empty=True,
            )
            if chosen & {"app_get", "app_install"}
            else ""
        )
        app_branch = _resolve_branch_for_prompt(
            console, app_url, frappe_branch, detect=not dry_run
        )
        ssl_email = (
            _ask_validated(
                console,
                "Certificate email",
                validate_email,
                default=previous.get("ssl_email"),
            )
            if "ssl_setup" in chosen
            else ""
        )
        passwordless = (
            terminal.confirm(
                console,
                "Enable passwordless bench restart for this user?",
                default=False,
            )
            if "sudoers_setup" in chosen
            else False
        )
        if not passwordless and "sudoers_setup" in selected:
            selected.remove("sudoers_setup")
        context = InstallContext(
            bench_name=bench_name,
            bench_parent=bench_parent,
            site_name=site_name,
            frappe_branch=frappe_branch,
            app_url=app_url,
            app_branch=app_branch,
            ssl_email=ssl_email,
            ubuntu_version=_detect_ubuntu_version(),
            sudo_password="",
            mariadb_root_password="",
            admin_password="",
            dry_run=dry_run,
            debug=debug,
            skip_ssl="ssl_setup" not in selected,
            enable_passwordless_restart=passwordless,
            selected_steps=selected.copy(),
            workflow=workflow,
        )
        print_plan(
            console, context, [step for step in ALL_STEPS if step.name in selected]
        )
        if terminal.interactive():
            action = terminal.choose(
                "Review plan",
                [
                    (
                        "continue",
                        "Preview plan"
                        if dry_run
                        else "Continue to credentials and install",
                    ),
                    ("edit", "Back: edit configuration"),
                    ("cancel", "Cancel"),
                ],
            )
            if action == "edit":
                previous = dict(
                    bench_name=bench_name,
                    bench_parent=bench_parent,
                    site_name=site_name,
                    frappe_branch=frappe_branch,
                    app_url=app_url,
                    ssl_email=ssl_email,
                )
                if "sudoers_setup" in chosen and "sudoers_setup" not in selected:
                    selected.append("sudoers_setup")
                continue
            if action == "cancel":
                raise click.Abort()
        elif not terminal.confirm(
            console,
            "Preview this plan?" if dry_run else "Apply this plan?",
            default=False,
        ):
            raise click.Abort()
        break
    if not dry_run:
        _credentials(console, context, set(selected))
    return context


def _credentials(console, context, pending):
    console.print("\n[bold]Credentials[/bold]  [dim]Passwords are never saved[/dim]")
    if pending - NO_SUDO:
        context.sudo_password = terminal.ask(console, "Sudo password", password=True)
    if pending & {"mariadb_secure", "site_create"}:
        context.mariadb_root_password = _prompt_mariadb_password(console)
    if "site_create" in pending:
        context.admin_password = os.environ.get("FP_ADMIN_PASSWORD") or terminal.ask(
            console, "Site Administrator password", password=True
        )
        if not context.admin_password:
            raise click.BadParameter("Administrator password cannot be empty.")


def collect_credentials_for_resume(
    console: Console, state: InstallState, skip_ssl=False, dry_run=False, debug=False
) -> InstallContext:
    print_header(console)
    selected = state.selected_steps or [step.name for step in ALL_STEPS]
    context = InstallContext(
        bench_name=state.bench_name,
        bench_parent=state.bench_parent,
        site_name=state.site_name,
        frappe_branch=state.frappe_branch,
        app_url=state.app_url,
        app_branch=state.app_branch,
        ssl_email=state.ssl_email,
        ubuntu_version=state.ubuntu_version,
        sudo_password="",
        mariadb_root_password="",
        admin_password="",
        dry_run=dry_run,
        debug=debug,
        skip_ssl=skip_ssl or state.skip_ssl,
        enable_passwordless_restart=state.enable_passwordless_restart,
        selected_steps=selected,
        workflow=state.workflow,
    )
    console.print("Resuming saved deployment", style="cyan")
    print_plan(
        console,
        context,
        [step for step in ALL_STEPS if step.name in selected],
        completed=set(state.completed_steps),
    )
    if not dry_run:
        pending = set(selected) - set(state.completed_steps)
        if context.skip_ssl:
            pending.discard("ssl_setup")
        if any(
            name in state.completed_steps for name in ("ssl_setup", "production_setup")
        ):
            pending.add("production_setup")
        _credentials(console, context, pending)
    return context
