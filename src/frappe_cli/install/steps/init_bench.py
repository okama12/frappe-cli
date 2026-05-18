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
