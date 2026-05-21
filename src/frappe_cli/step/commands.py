"""One Click command per wizard step under `fp step <name>`.

The wizard's `ALL_STEPS` is the canonical pipeline; this module wires each
of those `InstallStep` classes to a Click command with bespoke flags so
each step can be re-run individually with proper --help and option
validation. A `list` command also enumerates every step + its description.
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from frappe_cli.install.steps import ALL_STEPS
from frappe_cli.install.steps.app import AppGetStep, AppInstallStep
from frappe_cli.install.steps.bench import BenchInstallStep
from frappe_cli.install.steps.dns_multitenant import DnsMultitenantStep
from frappe_cli.install.steps.init_bench import BenchInitStep
from frappe_cli.install.steps.mariadb import MariaDBInstallStep, MariaDBSecureStep
from frappe_cli.install.steps.nodejs import NodeJSStep
from frappe_cli.install.steps.production import BenchRestartStep, ProductionSetupStep
from frappe_cli.install.steps.redis import RedisStep
from frappe_cli.install.steps.site import SiteCreateStep
from frappe_cli.install.steps.ssl import SSLSetupStep
from frappe_cli.install.steps.system import SystemDepsStep, SystemUpdateStep
from frappe_cli.install.steps.uv_check import UvCheckStep
from frappe_cli.install.steps.wkhtmltopdf import WkhtmltopdfStep

from ._runner import build_context, run_step

console = Console()


# ── shared option groups ─────────────────────────────────────────────────────


def common_options(f):
    """--dry-run / --debug / --force apply to every step command."""
    f = click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Run the step even when check() reports it as already complete",
    )(f)
    f = click.option(
        "--debug", is_flag=True, default=False, help="Verbose subprocess output"
    )(f)
    f = click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Print commands without executing them",
    )(f)
    return f


def _bench_option(required: bool = True):
    return click.option(
        "--bench-name",
        required=required,
        prompt=required,
        help="Bench directory name (e.g. test5-bench, frappe-bench)",
    )


def _site_option(required: bool = True):
    return click.option(
        "--site-name",
        required=required,
        prompt=required,
        help="Site FQDN (e.g. test5.rashidiokama.com)",
    )


# ── infrastructure / OS-level steps ──────────────────────────────────────────


@click.command("system-update")
@common_options
def cmd_system_update(dry_run: bool, debug: bool, force: bool) -> None:
    """Run `apt-get update && upgrade` (skipped if updated within 24h)."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=True)
    run_step(SystemUpdateStep(), ctx, force=force)


@click.command("system-deps")
@common_options
def cmd_system_deps(dry_run: bool, debug: bool, force: bool) -> None:
    """Install Frappe's required apt packages (python3-dev, libssl-dev, ...)."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=True)
    run_step(SystemDepsStep(), ctx, force=force)


@click.command("uv-check")
@common_options
def cmd_uv_check(dry_run: bool, debug: bool, force: bool) -> None:
    """Verify `uv` is installed; install it via astral.sh if missing."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=False)
    run_step(UvCheckStep(), ctx, force=force)


@click.command("nodejs")
@common_options
def cmd_nodejs(dry_run: bool, debug: bool, force: bool) -> None:
    """Install Node.js (v18 on 22.04, v20 on 24.04) + global Yarn."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=True)
    run_step(NodeJSStep(), ctx, force=force)


@click.command("mariadb-install")
@click.option(
    "--mariadb-password",
    prompt=False,
    default="",
    envvar="FP_MARIADB_PASSWORD",
    show_envvar=True,
    help=(
        "Used by mariadb-secure only; safe to leave empty here. "
        "Prefer the FP_MARIADB_PASSWORD env var over passing on argv."
    ),
)
@common_options
def cmd_mariadb_install(
    mariadb_password: str, dry_run: bool, debug: bool, force: bool
) -> None:
    """Install MariaDB server + write the Frappe utf8mb4 config."""
    ctx = build_context(
        mariadb_root_password=mariadb_password,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=True,
    )
    run_step(MariaDBInstallStep(), ctx, force=force)


@click.command("mariadb-secure")
@click.option(
    "--mariadb-password",
    required=True,
    prompt="MariaDB root password",
    hide_input=True,
    envvar="FP_MARIADB_PASSWORD",
    show_envvar=True,
    help=(
        "New MariaDB root password to set. "
        "Prefer the FP_MARIADB_PASSWORD env var over passing on argv "
        "(argv is world-readable via /proc/<pid>/cmdline)."
    ),
)
@common_options
def cmd_mariadb_secure(
    mariadb_password: str, dry_run: bool, debug: bool, force: bool
) -> None:
    """Set MariaDB root password + remove anonymous users / test DB."""
    ctx = build_context(
        mariadb_root_password=mariadb_password,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=True,
    )
    run_step(MariaDBSecureStep(), ctx, force=force)


@click.command("redis")
@common_options
def cmd_redis(dry_run: bool, debug: bool, force: bool) -> None:
    """Install Redis server and enable+start it (skipped if PING returns PONG)."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=True)
    run_step(RedisStep(), ctx, force=force)


@click.command("wkhtmltopdf")
@common_options
def cmd_wkhtmltopdf(dry_run: bool, debug: bool, force: bool) -> None:
    """Install wkhtmltopdf + its X11 font dependencies."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=True)
    run_step(WkhtmltopdfStep(), ctx, force=force)


# ── bench lifecycle steps ────────────────────────────────────────────────────


@click.command("bench-install")
@common_options
def cmd_bench_install(dry_run: bool, debug: bool, force: bool) -> None:
    """Install `frappe-bench` via `uv tool install` (skipped if already on PATH)."""
    ctx = build_context(dry_run=dry_run, debug=debug, needs_sudo=False)
    run_step(BenchInstallStep(), ctx, force=force)


@click.command("bench-init")
@_bench_option()
@click.option(
    "--frappe-branch",
    default="version-15",
    show_default=True,
    help="Frappe branch to initialise the bench with",
)
@common_options
def cmd_bench_init(
    bench_name: str, frappe_branch: str, dry_run: bool, debug: bool, force: bool
) -> None:
    """`bench init <name> --frappe-branch <branch>` (skipped if already initialised)."""
    ctx = build_context(
        bench_name=bench_name,
        frappe_branch=frappe_branch,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=False,
    )
    run_step(BenchInitStep(), ctx, force=force)


@click.command("site-create")
@_bench_option()
@_site_option()
@click.option(
    "--mariadb-password",
    required=True,
    prompt="MariaDB root password",
    hide_input=True,
    envvar="FP_MARIADB_PASSWORD",
    show_envvar=True,
    help=(
        "Required to create the site's database. "
        "Prefer FP_MARIADB_PASSWORD env var over argv."
    ),
)
@click.option(
    "--admin-password",
    required=True,
    prompt="Administrator password",
    hide_input=True,
    envvar="FP_ADMIN_PASSWORD",
    show_envvar=True,
    help=(
        "Initial password for the site's Administrator user. "
        "Prefer FP_ADMIN_PASSWORD env var over argv."
    ),
)
@common_options
def cmd_site_create(
    bench_name: str,
    site_name: str,
    mariadb_password: str,
    admin_password: str,
    dry_run: bool,
    debug: bool,
    force: bool,
) -> None:
    """`bench new-site <site>` against the given bench."""
    ctx = build_context(
        bench_name=bench_name,
        site_name=site_name,
        mariadb_root_password=mariadb_password,
        admin_password=admin_password,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=False,
    )
    run_step(SiteCreateStep(), ctx, force=force)


@click.command("app-get")
@_bench_option()
@click.option(
    "--app-url",
    required=True,
    help="App repo URL or short name (e.g. erpnext, https://github.com/frappe/erpnext)",
)
@click.option(
    "--app-branch",
    default=None,
    help=(
        "App branch to clone. "
        "Defaults to version-15 for official Frappe apps (erpnext, hrms…) "
        "or 'main' for custom apps. "
        "Branch detection is attempted automatically if omitted."
    ),
)
@common_options
def cmd_app_get(
    bench_name: str,
    app_url: str,
    app_branch: str | None,
    dry_run: bool,
    debug: bool,
    force: bool,
) -> None:
    """`bench get-app <url> --branch <branch>` (clones into apps/)."""
    from frappe_cli.utils.git_repo import resolve_app_branch

    if app_branch is None:
        resolved, hint = resolve_app_branch(app_url, frappe_branch="version-15")
        if hint:
            import click as _click

            _click.echo(f"Warning: {hint}", err=True)
        app_branch = resolved

    ctx = build_context(
        bench_name=bench_name,
        app_url=app_url,
        app_branch=app_branch,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=False,
    )
    run_step(AppGetStep(), ctx, force=force)


@click.command("dns-multitenant")
@_bench_option()
@common_options
def cmd_dns_multitenant(
    bench_name: str, dry_run: bool, debug: bool, force: bool
) -> None:
    """`bench config dns_multitenant on` — required before production for FQDN sites."""
    ctx = build_context(
        bench_name=bench_name, dry_run=dry_run, debug=debug, needs_sudo=False
    )
    run_step(DnsMultitenantStep(), ctx, force=force)


@click.command("production")
@_bench_option()
@common_options
def cmd_production(bench_name: str, dry_run: bool, debug: bool, force: bool) -> None:
    """`bench setup production` + self-heal supervisor symlink + hard-verify
    `supervisorctl status` RUNNING and Redis PONG on bench's queue/cache/socketio."""
    ctx = build_context(
        bench_name=bench_name, dry_run=dry_run, debug=debug, needs_sudo=True
    )
    run_step(ProductionSetupStep(), ctx, force=force)


@click.command("app-install")
@_bench_option()
@_site_option()
@click.option(
    "--app-url",
    required=True,
    help="Same value as passed to app-get; only the trailing app name is used",
)
@common_options
def cmd_app_install(
    bench_name: str,
    site_name: str,
    app_url: str,
    dry_run: bool,
    debug: bool,
    force: bool,
) -> None:
    """`bench --site <site> install-app <app>`."""
    ctx = build_context(
        bench_name=bench_name,
        site_name=site_name,
        app_url=app_url,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=False,
    )
    run_step(AppInstallStep(), ctx, force=force)


@click.command("bench-restart")
@_bench_option()
@common_options
def cmd_bench_restart(bench_name: str, dry_run: bool, debug: bool, force: bool) -> None:
    """`supervisorctl reread && update && systemctl reload nginx` to pick up new app code."""
    # bench_restart's check() skips when no app_url; pass a dummy non-empty value
    # so the user's explicit invocation actually runs.
    ctx = build_context(
        bench_name=bench_name,
        app_url="dummy",
        dry_run=dry_run,
        debug=debug,
        needs_sudo=True,
    )
    run_step(BenchRestartStep(), ctx, force=force)


@click.command("ssl")
@_bench_option()
@_site_option()
@click.option(
    "--ssl-email",
    default="",
    show_default=False,
    help="Email for Let's Encrypt account registration (first run on the host only)",
)
@common_options
def cmd_ssl(
    bench_name: str,
    site_name: str,
    ssl_email: str,
    dry_run: bool,
    debug: bool,
    force: bool,
) -> None:
    """`bench setup lets-encrypt <site>` — issues an HTTPS cert and updates bench's nginx."""
    ctx = build_context(
        bench_name=bench_name,
        site_name=site_name,
        ssl_email=ssl_email,
        dry_run=dry_run,
        debug=debug,
        needs_sudo=True,
    )
    run_step(SSLSetupStep(), ctx, force=force)


# ── discovery ────────────────────────────────────────────────────────────────


@click.command("list")
def list_steps() -> None:
    """List every wizard step (in execution order) with its description."""
    table = Table(show_header=True, header_style="bold magenta", title="Wizard steps")
    table.add_column("#", style="dim", width=3)
    table.add_column("Step (CLI name)")
    table.add_column("Description")

    # CLI command names mirror Click command IDs declared above (kebab-case).
    cli_name_overrides = {
        "system_update": "system-update",
        "system_deps": "system-deps",
        "uv_check": "uv-check",
        "mariadb_install": "mariadb-install",
        "mariadb_secure": "mariadb-secure",
        "bench_install": "bench-install",
        "bench_init": "bench-init",
        "site_create": "site-create",
        "app_get": "app-get",
        "dns_multitenant": "dns-multitenant",
        "production_setup": "production",
        "app_install": "app-install",
        "bench_restart": "bench-restart",
        "ssl_setup": "ssl",
    }

    for idx, step_instance in enumerate(ALL_STEPS, 1):
        cli_name = cli_name_overrides.get(step_instance.name, step_instance.name)
        table.add_row(str(idx), f"[cyan]{cli_name}[/cyan]", step_instance.description)

    console.print(table)
    console.print(
        "\nRun any step with [bold]fp step <name> --help[/bold] to see flags."
    )


ALL_STEP_COMMANDS = [
    cmd_system_update,
    cmd_system_deps,
    cmd_uv_check,
    cmd_nodejs,
    cmd_mariadb_install,
    cmd_mariadb_secure,
    cmd_redis,
    cmd_wkhtmltopdf,
    cmd_bench_install,
    cmd_bench_init,
    cmd_site_create,
    cmd_app_get,
    cmd_dns_multitenant,
    cmd_production,
    cmd_app_install,
    cmd_bench_restart,
    cmd_ssl,
]
