import shutil
from pathlib import Path

from .base import InstallStep


class BenchInitStep(InstallStep):
    name = "bench_init"
    description = "Initialize bench"

    def check(self, ctx) -> bool:
        # On a non-fresh VPS the target bench dir may already exist with a
        # fully-installed frappe. Treat that as a successful skip and tell
        # the user so they don't think the wizard silently overwrote it.
        already = (ctx.bench_path / "apps" / "frappe").exists()
        if already and ctx.log_fn:
            ctx.log_fn(
                f"Bench {ctx.bench_name} already initialised at {ctx.bench_path}"
            )
        return already

    def run(self, ctx) -> None:
        # A bench dir that exists without apps/frappe is a partial init from a
        # previously interrupted run. Remove it so bench starts from a clean state
        # rather than trying to reconcile stale app state.
        if ctx.bench_path.exists() and not (ctx.bench_path / "apps" / "frappe").exists():
            if ctx.log_fn:
                ctx.log_fn(
                    f"Removing partial bench at {ctx.bench_path} before re-initialising"
                )
            shutil.rmtree(ctx.bench_path)

        self._run(
            ctx,
            [
                "bench",
                "init",
                ctx.bench_name,
                "--frappe-branch",
                ctx.frappe_branch,
            ],
            cwd=str(Path.home()),
        )

    def rollback(self, ctx) -> None:
        if ctx.bench_path.exists():
            if ctx.log_fn:
                ctx.log_fn(f"Rolling back: removing {ctx.bench_path}")
            shutil.rmtree(ctx.bench_path, ignore_errors=True)
