"""Primary short commands; all installation work stays in the shared steps."""

from pathlib import Path

import click
from rich.console import Console

from frappe_cli.dev.context import frappe_branch, write_active_site
from frappe_cli.install.steps.app import AppGetStep, AppInstallStep
from frappe_cli.install.steps.bench import BenchInstallStep
from frappe_cli.install.steps.dns_multitenant import DnsMultitenantStep
from frappe_cli.install.steps.init_bench import BenchInitStep
from frappe_cli.install.steps.mariadb import MariaDBInstallStep, MariaDBSecureStep
from frappe_cli.install.steps.nodejs import NodeJSStep
from frappe_cli.install.steps.production import BenchRestartStep, ProductionSetupStep
from frappe_cli.install.steps.redis import RedisStep
from frappe_cli.install.steps.site import SiteCreateStep
from frappe_cli.install.steps.system import SystemDepsStep, SystemUpdateStep
from frappe_cli.install.steps.uv_check import UvCheckStep
from frappe_cli.install.steps.wkhtmltopdf import WkhtmltopdfStep
from frappe_cli.step._runner import build_context, run_step
from frappe_cli.ui import terminal
from frappe_cli.utils.git_repo import resolve_app_branch
from frappe_cli.utils.targets import bench_target, print_target, site_target, validated
from frappe_cli.utils.validators import validate_bench_name, validate_site_name


def make_action(name, step_type, *, scope="server", argument=None, sudo=True):
    params = [
        click.Option(["--dry-run"], is_flag=True, help="Preview without changes."),
        click.Option(["--debug"], is_flag=True, help="Show detailed output."),
        click.Option(
            ["--force"], is_flag=True, help="Run even when already configured."
        ),
    ]
    if argument:
        params.insert(0, click.Argument([argument], required=False))
    if scope != "server" and argument != "name":
        params.append(
            click.Option(
                ["--bench", "--bench-name"],
                help="Bench name or absolute path; detected from cwd.",
            )
        )
    if scope == "site" and argument != "domain":
        params.append(
            click.Option(
                ["--site", "-s", "--site-name"],
                help="Override the active site for this command.",
            )
        )
    if argument == "name" or step_type is AppGetStep:
        params.append(
            click.Option(["--branch"], default=None, help="Frappe or app branch.")
        )
    if argument == "name":
        params.append(
            click.Option(
                ["--path"],
                type=click.Path(exists=True, file_okay=False, path_type=Path),
                help="Parent directory for the new bench; defaults to home.",
            )
        )

    def invoke(**values):
        console = Console()
        dry_run = values.get("dry_run", False)
        kwargs = {
            "dry_run": dry_run,
            "debug": values.get("debug", False),
            "needs_sudo": sudo,
        }
        if argument == "name":
            bench_name = values.get("name") or terminal.ask(
                console, "Bench name", default="frappe-bench"
            )
            kwargs["bench_name"] = validated(bench_name, validate_bench_name)
            kwargs["frappe_branch"] = values.get("branch") or "version-15"
            parent = values.get("path") or Path.home()
            kwargs["bench_parent"] = str(parent.resolve())
        elif scope != "server":
            bench = bench_target(values.get("bench"))
            kwargs.update(bench_name=bench.name, bench_parent=str(bench.parent))
            if scope == "site":
                kwargs["site_name"] = (
                    validated(
                        values.get("domain")
                        or terminal.ask(console, "New site domain"),
                        validate_site_name,
                    )
                    if argument == "domain"
                    else site_target(bench, values.get("site"))
                )
            print_target(console, bench, kwargs.get("site_name", ""))
        if argument == "app":
            app = values.get("app") or terminal.ask(console, "App name or repository")
            kwargs["app_url"] = app
            installed_branch = frappe_branch(bench) or "version-15"
            branch, hint = (
                resolve_app_branch(app, frappe_branch=installed_branch)
                if not dry_run
                and values.get("branch") is None
                and step_type is AppGetStep
                else (values.get("branch") or installed_branch, "")
            )
            kwargs["app_branch"] = branch
            if hint:
                console.print(hint, markup=False)
        if step_type is BenchRestartStep:
            kwargs["app_url"] = "reload"
        if step_type in {MariaDBSecureStep, SiteCreateStep} and not dry_run:
            import os

            kwargs["mariadb_root_password"] = os.environ.get(
                "FP_MARIADB_PASSWORD"
            ) or terminal.ask(console, "MariaDB root password", password=True)
        if step_type is SiteCreateStep and not dry_run:
            import os

            kwargs["admin_password"] = os.environ.get(
                "FP_ADMIN_PASSWORD"
            ) or terminal.ask(console, "Site Administrator password", password=True)
        context = build_context(**kwargs)
        run_step(step_type(), context, force=values.get("force", False))
        if step_type is SiteCreateStep and not dry_run:
            write_active_site(context.bench_path, context.site_name)

    return click.Command(
        name, callback=invoke, params=params, help=step_type.description + "."
    )


DIRECT_ACTIONS = [
    make_action("os-update", SystemUpdateStep),
    make_action("deps", SystemDepsStep),
    make_action("uv", UvCheckStep, sudo=False),
    make_action("node", NodeJSStep),
    make_action("database", MariaDBInstallStep),
    make_action("db-secure", MariaDBSecureStep),
    make_action("redis", RedisStep),
    make_action("pdf", WkhtmltopdfStep),
    make_action("bench", BenchInstallStep, sudo=False),
    make_action("init", BenchInitStep, scope="bench", argument="name", sudo=False),
    make_action("new", SiteCreateStep, scope="site", argument="domain", sudo=False),
    make_action("get", AppGetStep, scope="bench", argument="app", sudo=False),
    make_action("add", AppInstallStep, scope="site", argument="app", sudo=False),
    make_action("dns", DnsMultitenantStep, scope="bench", sudo=False),
    make_action("prod", ProductionSetupStep, scope="bench"),
    make_action("reload", BenchRestartStep, scope="bench"),
]
