import getpass
import subprocess
from pathlib import Path

from .base import InstallStep


class ProductionSetupStep(InstallStep):
    name = "production_setup"
    description = "Setup production (nginx + supervisor)"

    _SUDOERS_TEMP = "/etc/sudoers.d/frappe-installer-temp"

    def check(self, ctx) -> bool:
        bench_conf = Path(f"/etc/nginx/conf.d/{ctx.bench_name}.conf")
        return bench_conf.exists()

    def run(self, ctx) -> None:
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn("[dry-run] $ bench setup production <user> --yes")
            return
        current_user = getpass.getuser()
        # Grant temporary passwordless sudo so bench's internal sudo calls
        # (ansible install, nginx/supervisor config) never prompt for a password.
        # Removed unconditionally in the finally block.
        self._sudo(
            ctx,
            [
                "bash",
                "-c",
                f"echo '{current_user} ALL=(ALL) NOPASSWD:ALL'"
                f" > {self._SUDOERS_TEMP}"
                f" && chmod 440 {self._SUDOERS_TEMP}",
            ],
        )
        try:
            self._run(
                ctx,
                ["bench", "setup", "production", current_user, "--yes"],
                cwd=str(ctx.bench_path),
            )
        finally:
            subprocess.run(
                ["sudo", "-S", "rm", "-f", self._SUDOERS_TEMP],
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True,
            )


class BenchRestartStep(InstallStep):
    """Reload supervisor workers so they pick up newly installed app code."""

    name = "bench_restart"
    description = "Reload bench workers"

    def check(self, ctx) -> bool:
        return not ctx.app_url

    def run(self, ctx) -> None:
        self._sudo(ctx, ["supervisorctl", "reload"])
