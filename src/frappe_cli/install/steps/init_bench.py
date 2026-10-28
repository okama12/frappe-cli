from uuid import uuid4

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
        # Preserve interrupted runs; an unrelated directory is never disposable.
        if (
            not ctx.dry_run
            and ctx.bench_path.exists()
            and not (ctx.bench_path / "apps" / "frappe").exists()
        ):
            backup = ctx.bench_path.with_name(
                f"{ctx.bench_name}.partial-{uuid4().hex[:8]}"
            )
            ctx.bench_path.rename(backup)
            if ctx.log_fn:
                ctx.log_fn(
                    f"Preserved partial bench at {backup} before re-initialising"
                )

        self._run(
            ctx,
            [
                "bench",
                "init",
                ctx.bench_name,
                "--frappe-branch",
                ctx.frappe_branch,
            ],
            cwd=str(ctx.bench_path.parent),
        )

    def rollback(self, ctx) -> None:
        if ctx.log_fn:
            ctx.log_fn(
                f"Preserving installation files at {ctx.bench_path} for recovery"
            )
