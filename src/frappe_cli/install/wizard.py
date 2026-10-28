import time
from contextlib import nullcontext

import click
from rich.console import Console
from rich.live import Live
from rich.text import Text

from ..dev.context import write_active_site
from ..ui import terminal
from ..ui.panels import print_error, print_success
from ..ui.prompts import collect_credentials_for_resume, collect_inputs
from ..ui.steps import StepListRenderer
from .recovery import explain
from .state import InstallState, clear_state, load_state, save_state, state_exists
from .steps import ALL_STEPS
from .steps.base import StepError

console = Console()
# Revalidate observable state; do not repeat one-time credential mutations.
RECHECK = {
    "bench_init",
    "site_create",
    "app_get",
    "production_setup",
    "ssl_setup",
    "nodejs",
    "redis",
    "bench_install",
    "uv_check",
    "wkhtmltopdf",
}
RETRY_SAFE = {
    "system_update",
    "system_deps",
    "mariadb_install",
    "redis",
    "bench_install",
}


def _redact(value: str, ctx) -> str:
    for secret in sorted(
        (ctx.sudo_password, ctx.mariadb_root_password, ctx.admin_password),
        key=len,
        reverse=True,
    ):
        if secret:
            value = value.replace(secret, "[redacted]")
    return value


def _persist(ctx, completed):
    save_state(
        InstallState(
            bench_name=ctx.bench_name,
            bench_parent=ctx.bench_parent,
            site_name=ctx.site_name,
            frappe_branch=ctx.frappe_branch,
            app_url=ctx.app_url,
            app_branch=ctx.app_branch,
            ssl_email=ctx.ssl_email,
            ubuntu_version=ctx.ubuntu_version,
            enable_passwordless_restart=ctx.enable_passwordless_restart,
            selected_steps=ctx.selected_steps,
            workflow=ctx.workflow,
            skip_ssl=ctx.skip_ssl,
            completed_steps=[step.name for step in ALL_STEPS if step.name in completed],
        )
    )


@click.command()
@click.option(
    "--resume",
    is_flag=True,
    help="Resume the saved plan and revalidate completed resources.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Review the plan without executing commands or saving state.",
)
@click.option("--debug", is_flag=True, help="Show full failure details.")
@click.option("--skip-ssl", is_flag=True, help="Leave HTTPS for later.")
@click.option(
    "--components",
    default=None,
    help="Comma-separated component IDs; omit a value with fp setup --task custom to select interactively.",
)
@click.option(
    "--profile",
    type=click.Choice(["production", "development"]),
    default="production",
    hidden=True,
)
def wizard(resume, dry_run, debug, skip_ssl, components, profile):
    """Guided production installation with review, progress, and recovery."""
    if resume:
        if components is not None:
            raise click.UsageError("--resume uses the saved component selection.")
        if not state_exists():
            raise click.ClickException("No saved installation. Start with fp setup.")
        try:
            state = load_state()
        except (OSError, ValueError, TypeError) as exc:
            raise click.ClickException(
                f"Cannot read the saved installation: {exc}"
            ) from exc
        ctx = collect_credentials_for_resume(
            console, state, skip_ssl=skip_ssl, dry_run=dry_run, debug=debug
        )
        completed = set(state.completed_steps)
    else:
        if not dry_run and state_exists():
            if not terminal.confirm(
                console,
                "A saved installation exists. Replace its progress with a new plan?",
                default=False,
            ):
                raise click.ClickException(
                    "Saved progress preserved. Run fp setup --resume."
                )
        kwargs = dict(dry_run=dry_run, debug=debug, skip_ssl=skip_ssl)
        if profile == "development":
            components = "site_create,app_get"
        if components is not None:
            kwargs["components"] = [
                part.strip() for part in components.split(",") if part.strip()
            ]
        ctx = collect_inputs(console, **kwargs)
        if profile == "development":
            ctx.workflow = "development"
        completed = set()

    active = [
        step
        for step in ALL_STEPS
        if (not ctx.selected_steps or step.name in ctx.selected_steps)
        and not (ctx.skip_ssl and step.name == "ssl_setup")
    ]
    if dry_run:
        console.print(
            "\nPreview complete. No installation commands ran; saved progress is unchanged.",
            style="yellow",
        )
        return
    if ctx.ubuntu_version not in {"22.04", "24.04"}:
        raise click.ClickException(
            f"Unsupported Ubuntu version: {ctx.ubuntu_version}. This installer supports 22.04 and 24.04."
        )
    _persist(ctx, completed)
    renderer = StepListRenderer([step.description for step in active])
    animated = terminal.interactive()

    def log(line):
        clean = _redact(line, ctx)
        renderer.add_log(clean)
        if not animated:
            console.print(Text(clean, style="dim"))

    ctx.log_fn = log
    for index, step in enumerate(active, 1):
        renderer.set_current(step.description)
        retries = 0
        while True:
            if not animated:
                console.print(
                    Text(f"[{index}/{len(active)}] {step.description}", style="cyan")
                )
            try:
                with Live(
                    renderer,
                    console=console,
                    refresh_per_second=6,
                    vertical_overflow="crop",
                    transient=True,
                ) if animated else nullcontext():
                    renderer.mark_running(step.description)
                    if step.name in completed and step.name not in RECHECK:
                        renderer.mark_skipped(step.description)
                    else:
                        already = step.check(ctx)
                        if already:
                            renderer.mark_skipped(step.description)
                        else:
                            if step.name in completed and step.name in {
                                "site_create",
                                "bench_init",
                            }:
                                raise StepError(
                                    "A previously completed resource is missing.",
                                    hint=f"Inspect {ctx.bench_path} before creating a new deployment. Saved site/bench creation will not be repeated automatically.",
                                )
                            step.run(ctx)
                            renderer.mark_done(step.description)
                    completed.add(step.name)
                    _persist(ctx, completed)
                if not animated:
                    console.print("  Complete", style="green")
                break
            except KeyboardInterrupt as exc:
                console.print(
                    "\nInterrupted. Progress preserved; run fp setup --resume.",
                    style="yellow",
                )
                raise click.Abort() from exc
            except Exception as exc:
                renderer.mark_failed(step.description)
                error = (
                    exc
                    if isinstance(exc, StepError)
                    else StepError(f"{type(exc).__name__}: {exc}")
                )
                guidance, transient = explain(error)
                if transient and step.name in RETRY_SAFE and retries < 2:
                    retries += 1
                    console.print(
                        f"Temporary failure. Retrying ({retries}/2) in {retries * 2}s…",
                        style="yellow",
                    )
                    time.sleep(retries * 2)
                    continue
                details = _redact(error.hint, ctx)
                if animated:
                    console.print(renderer)
                print_error(
                    console,
                    step.description,
                    _redact(error.message, ctx),
                    guidance
                    + (
                        "\n\n"
                        + (details if debug else "\n".join(details.splitlines()[-12:]))
                        if details
                        else ""
                    ),
                )
                if not animated:
                    raise click.exceptions.Exit(1) from exc
                while True:
                    action = terminal.choose(
                        "Next action",
                        [
                            ("retry", "Retry this step"),
                            ("details", "Inspect failure details"),
                            ("exit", "Save progress and exit"),
                        ],
                    )
                    if action == "details":
                        console.print(Text(details or _redact(str(exc), ctx)))
                        continue
                    if action == "exit":
                        raise click.exceptions.Exit(1) from exc
                    break

    if (
        ctx.site_name
        and (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").is_file()
    ):
        write_active_site(ctx.bench_path, ctx.site_name)
    clear_state()
    if animated:
        console.print(renderer)
    if ctx.workflow == "custom":
        console.print("\n✓ Selected components completed.", style="green")
        if ctx.bench_name:
            console.print(Text(f"Bench: {ctx.bench_path}"))
    elif ctx.workflow == "development":
        console.print("\n✓ Development bench and site prepared.", style="green")
        console.print(Text(f"Bench: {ctx.bench_path}"))
        console.print("Start development processes from this bench with fp start.")
        if ctx.app_url:
            console.print(
                Text(
                    f"Then install the downloaded app in another terminal: fp add {ctx.app_name}"
                )
            )
    else:
        print_success(console, ctx)
