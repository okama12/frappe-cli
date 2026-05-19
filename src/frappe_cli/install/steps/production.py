import getpass
import json
import socket
import subprocess
import time
from pathlib import Path

from .base import InstallStep, StepError


class ProductionSetupStep(InstallStep):
    name = "production_setup"
    description = "Setup production (nginx + supervisor)"

    def check(self, ctx) -> bool:
        nginx_conf = Path(f"/etc/nginx/conf.d/{ctx.bench_name}.conf")
        supervisor_conf = Path(f"/etc/supervisor/conf.d/{ctx.bench_name}.conf")
        return nginx_conf.exists() and supervisor_conf.exists()

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

        # Self-heal supervisor: on multi-bench servers `bench setup production`
        # sometimes does NOT add the new bench's supervisor.conf into
        # /etc/supervisor/conf.d/. Without this symlink, `supervisorctl reread`
        # is a no-op, Redis never starts for this bench, and the subsequent
        # `bench install-app` fails with "Connection refused" on the queue port
        # (e.g. 11003). Manually verified against test3-bench / test4-bench.
        supervisor_target = Path(f"/etc/supervisor/conf.d/{ctx.bench_name}.conf")
        bench_supervisor = ctx.bench_path / "config" / "supervisor.conf"
        if not supervisor_target.exists() and bench_supervisor.exists():
            if ctx.log_fn:
                ctx.log_fn(f"Linking supervisor config: {supervisor_target}")
            self._sudo(
                ctx, ["ln", "-sf", str(bench_supervisor), str(supervisor_target)]
            )

        # Load the new bench's supervisor config without restarting other benches.
        # `service supervisor restart` kills all benches on multi-bench servers;
        # reread+update only adds the new bench's process group.
        self._sudo(ctx, ["supervisorctl", "reread"])
        self._sudo(ctx, ["supervisorctl", "update"])

        # `bench restart` reloads web + workers via supervisor so newly written
        # app code is picked up. Mirrors the manual runbook (Step 4.3).
        self._run(ctx, ["bench", "restart"], cwd=str(ctx.bench_path))

        # Hard verification: raise StepError early if processes did not start.
        # The previous version only logged a warning, so `install-app` would
        # then fail with an opaque Redis error. We surface the supervisor +
        # Redis state directly.
        self._verify_supervisor_running(ctx)
        self._verify_redis_pong(ctx)

    def _verify_supervisor_running(self, ctx, timeout: int = 60) -> None:
        """Poll `supervisorctl status` until all <bench>-* processes are RUNNING."""
        if ctx.log_fn:
            ctx.log_fn(f"Verifying supervisor processes for {ctx.bench_name}...")

        prefix = f"{ctx.bench_name}-"
        deadline = time.time() + timeout
        last_status = ""
        while time.time() < deadline:
            try:
                proc = subprocess.run(
                    ["sudo", "-S", "supervisorctl", "status"],
                    input=(ctx.sudo_password + "\n").encode(),
                    capture_output=True,
                    timeout=15,
                )
                last_status = proc.stdout.decode(errors="replace") + proc.stderr.decode(
                    errors="replace"
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                last_status = f"supervisorctl status failed: {e}"
                time.sleep(3)
                continue

            bench_lines = [line for line in last_status.splitlines() if prefix in line]
            if bench_lines and all("RUNNING" in line for line in bench_lines):
                if ctx.log_fn:
                    ctx.log_fn(f"Supervisor OK: {len(bench_lines)} processes RUNNING")
                return
            time.sleep(3)

        raise StepError(
            f"Supervisor processes did not reach RUNNING for {ctx.bench_name}",
            hint=last_status.strip()
            or "No matching supervisor processes found. Check supervisor.conf symlink.",
        )

    def _verify_redis_pong(self, ctx, timeout: int = 60) -> None:
        """Open TCP to the bench's Redis queue + cache ports and verify PONG.

        Uses the RESP protocol directly (no `redis-cli` dependency on PATH).
        Reads ports from `sites/common_site_config.json`.
        """
        ports = self._bench_redis_ports(ctx)
        if not ports:
            if ctx.log_fn:
                ctx.log_fn(
                    "Skipping Redis ping: ports unreadable from common_site_config.json"
                )
            return

        if ctx.log_fn:
            ctx.log_fn(f"Pinging bench Redis on ports {sorted(ports)}...")

        for port in sorted(ports):
            deadline = time.time() + timeout
            ok = False
            last_err = ""
            while time.time() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
                        s.sendall(b"*1\r\n$4\r\nPING\r\n")
                        data = s.recv(64)
                    if data.startswith(b"+PONG"):
                        ok = True
                        if ctx.log_fn:
                            ctx.log_fn(f"Redis on port {port}: PONG")
                        break
                    last_err = f"unexpected reply: {data!r}"
                except OSError as e:
                    last_err = str(e)
                time.sleep(2)
            if not ok:
                raise StepError(
                    f"Bench Redis did not respond on port {port}",
                    hint=last_err
                    or "Check `sudo supervisorctl status` and supervisor.conf symlink.",
                )

    def _bench_redis_ports(self, ctx) -> list[int]:
        """Extract queue + cache + socketio ports from common_site_config.json."""
        config_path = ctx.bench_path / "sites" / "common_site_config.json"
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (OSError, ValueError):
            return []
        ports: set[int] = set()
        for key in ("redis_queue", "redis_cache", "redis_socketio"):
            url = config.get(key)
            if not url:
                continue
            try:
                ports.add(int(url.rsplit(":", 1)[-1]))
            except ValueError:
                continue
        return list(ports)

    # Kept for backwards compatibility with older callers; `_verify_redis_pong`
    # supersedes it but reuses the same port-parsing logic above.
    def _wait_for_bench_redis(self, ctx, timeout: int = 60) -> None:
        ports = self._bench_redis_ports(ctx)
        port = ports[0] if ports else 11001
        if ctx.log_fn:
            ctx.log_fn(f"Waiting for Redis queue on port {port}...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
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
