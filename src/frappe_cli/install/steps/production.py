import getpass
import subprocess
from pathlib import Path

from .base import InstallStep, StepError


class ProductionSetupStep(InstallStep):
    name = "production_setup"
    description = "Setup production (nginx + supervisor)"

    def check(self, ctx) -> bool:
        bench_conf = Path(f"/etc/nginx/conf.d/{ctx.bench_name}.conf")
        return bench_conf.exists()

    def run(self, ctx) -> None:
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn("[dry-run] $ bench setup production <user> --yes")
            return
        current_user = getpass.getuser()
        # Warm the sudo credential cache. bench setup production calls sudo
        # internally without -S/-A, so it needs a cached session, not stdin.
        self._sudo(ctx, ["-v"])
        result = subprocess.run(
            ["bench", "setup", "production", current_user, "--yes"],
            cwd=str(ctx.bench_path),
            capture_output=True,
            text=True,
            env=self._local_bin_env(),
        )
        if result.returncode != 0:
            raise StepError("bench setup production failed", hint=result.stderr)


class BenchRestartStep(InstallStep):
    """Reload supervisor workers so they pick up newly installed app code."""

    name = "bench_restart"
    description = "Reload bench workers"

    def check(self, ctx) -> bool:
        return not ctx.app_url

    def run(self, ctx) -> None:
        self._sudo(ctx, ["supervisorctl", "reload"])
