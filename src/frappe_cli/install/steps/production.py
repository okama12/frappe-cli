import getpass
from pathlib import Path

from .base import InstallStep


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
        # Use the absolute bench path so sudo can find it without PATH
        # manipulation. Running bench under sudo means its internal sudo calls
        # are already root and never prompt for a password.
        bench_bin = str(Path.home() / ".local" / "bin" / "bench")
        self._sudo(
            ctx,
            [bench_bin, "setup", "production", current_user, "--yes"],
            cwd=str(ctx.bench_path),
        )


class BenchRestartStep(InstallStep):
    """Reload supervisor workers so they pick up newly installed app code."""

    name = "bench_restart"
    description = "Reload bench workers"

    def check(self, ctx) -> bool:
        return not ctx.app_url

    def run(self, ctx) -> None:
        self._sudo(ctx, ["supervisorctl", "reload"])
