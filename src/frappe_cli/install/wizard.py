import sys

import click
from rich.console import Console
from rich.live import Live

from ..ui.panels import print_error, print_success
from ..ui.prompts import collect_credentials_for_resume, collect_inputs
from ..ui.steps import StepListRenderer
from .state import InstallState, clear_state, load_state, save_state, state_exists
from .steps import ALL_STEPS
from .steps.base import StepError

console = Console()


@click.command()
@click.option("--resume", is_flag=True, help="Resume from the last failed step")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
@click.option("--debug", is_flag=True, help="Show full command output during execution")
@click.option(
    "--skip-ssl",
    is_flag=True,
    help="Skip SSL setup (for local/VM testing without a real domain)",
)
def wizard(resume, dry_run, debug, skip_ssl):
    """Interactive production installer for Frappe."""
    if resume:
        if not state_exists():
            console.print(
                "[red]No previous install state found. Run 'frappe install wizard'.[/red]"
            )
            sys.exit(1)
        state = load_state()
        ctx = collect_credentials_for_resume(
            console, state, skip_ssl=skip_ssl, dry_run=dry_run, debug=debug
        )
        completed_steps = set(state.completed_steps)
    else:
        ctx = collect_inputs(console, dry_run=dry_run, debug=debug, skip_ssl=skip_ssl)
        completed_steps = set()

    active_steps = [
        s for s in ALL_STEPS if not (ctx.skip_ssl and s.name == "ssl_setup")
    ]

    renderer = StepListRenderer([s.description for s in active_steps])
    ctx.log_fn = renderer.add_log

    for step in active_steps:
        if step.name in completed_steps:
            renderer.mark_skipped(step.description)

    failed = None

    with Live(renderer, console=console, refresh_per_second=8):
        for step in active_steps:
            if step.name in completed_steps:
                continue

            renderer.set_current(step.description)
            renderer.mark_running(step.description)

            try:
                if step.check(ctx):
                    renderer.mark_skipped(step.description)
                else:
                    step.run(ctx)
                    renderer.mark_done(step.description)

                completed_steps.add(step.name)
                save_state(
                    InstallState(
                        bench_name=ctx.bench_name,
                        site_name=ctx.site_name,
                        frappe_branch=ctx.frappe_branch,
                        app_url=ctx.app_url,
                        app_branch=ctx.app_branch,
                        ssl_email=ctx.ssl_email,
                        ubuntu_version=ctx.ubuntu_version,
                        completed_steps=list(completed_steps),
                    )
                )

            except StepError as e:
                renderer.mark_failed(step.description)
                try:
                    step.rollback(ctx)
                except Exception:
                    pass
                failed = (step, e)
                break

    if failed:
        step, err = failed
        print_error(console, step.description, err.message, err.hint)
        sys.exit(1)

    clear_state()
    print_success(console, ctx)
