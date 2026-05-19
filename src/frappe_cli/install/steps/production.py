import getpass
import json
import socket
import time
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

        # nginx (www-data) must be able to traverse the home directory to serve
        # bench static files. Without o+x, every request returns 403 Forbidden.
        self._sudo(ctx, ["chmod", "o+x", str(Path.home())])

        # Load the new bench's supervisor config without restarting other benches.
        # `service supervisor restart` kills all benches on multi-bench servers;
        # reread+update only adds the new bench's process group.
        self._sudo(ctx, ["supervisorctl", "reread"])
        self._sudo(ctx, ["supervisorctl", "update"])

        # Block until the bench's Redis queue is accepting connections.
        # bench install-app connects to Redis immediately; if we proceed before
        # it's ready we get "Connection refused" on port 11001/11003/etc.
        self._wait_for_bench_redis(ctx)

    def _wait_for_bench_redis(self, ctx, timeout: int = 60) -> None:
        config_path = ctx.bench_path / "sites" / "common_site_config.json"
        port = 11001  # fallback default
        try:
            with open(config_path) as f:
                config = json.load(f)
            redis_url = config.get("redis_queue", f"redis://127.0.0.1:{port}")
            port = int(redis_url.rsplit(":", 1)[-1])
        except Exception:
            pass

        if ctx.log_fn:
            ctx.log_fn(f"Waiting for Redis queue on port {port}...")

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    if ctx.log_fn:
                        ctx.log_fn(f"Redis queue ready on port {port}")
                    return
            except OSError:
                time.sleep(2)

        if ctx.log_fn:
            ctx.log_fn(f"Warning: Redis on port {port} did not start within {timeout}s")


class BenchRestartStep(InstallStep):
    """Reload supervisor workers so they pick up newly installed app code."""

    name = "bench_restart"
    description = "Reload bench workers"

    def check(self, ctx) -> bool:
        return not ctx.app_url

    def run(self, ctx) -> None:
        self._sudo(ctx, ["supervisorctl", "reread"])
        self._sudo(ctx, ["supervisorctl", "update"])
        self._sudo(ctx, ["systemctl", "reload", "nginx"])
