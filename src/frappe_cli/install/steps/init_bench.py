import shutil
from pathlib import Path

from .base import InstallStep


class BenchInitStep(InstallStep):
    name = "bench_init"
    description = "Initialize bench"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "apps" / "frappe").exists()

    def run(self, ctx) -> None:
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
