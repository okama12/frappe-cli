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
        bench_bin = str(Path.home() / ".local" / "bin" / "bench")

        # bench's setup_production_prerequisites() runs:
        #   sudo python -m pip install ansible
        # That call fails in a non-TTY subprocess. Pre-installing ansible via
        # apt makes bench's find_executable("ansible") return a path, so it
        # skips the pip install and goes straight to the ansible playbook.
        self._sudo(ctx, ["apt-get", "install", "-y", "ansible"])

        # bench setup production requires UID 0, so we must run it under sudo.
        # sudo resets PATH to its secure default, which excludes ~/.local/bin.
        # Bench's ansible playbook calls `bench setup role <x>` as subprocesses
        # that inherit the env, so we pass PATH explicitly via `env` to ensure
        # bench can find itself throughout the playbook execution.
        bench_path = self._local_bin_env()["PATH"]
        self._sudo(
            ctx,
            [
                "env",
                f"PATH={bench_path}",
                bench_bin,
                "setup",
                "production",
                current_user,
                "--yes",
            ],
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
