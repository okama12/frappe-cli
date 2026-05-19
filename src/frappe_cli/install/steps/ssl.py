import subprocess
from pathlib import Path

from .base import InstallStep


class SSLSetupStep(InstallStep):
    name = "ssl_setup"
    description = "Configure SSL (Let's Encrypt)"

    def _cert_path(self, ctx) -> Path:
        return Path(f"/etc/letsencrypt/live/{ctx.site_name}/fullchain.pem")

    def check(self, ctx) -> bool:
        """Return True only if a cert already exists for THIS site.

        `/etc/letsencrypt/live/` is mode 700 root-owned as soon as any cert
        is issued, so a non-root `Path.exists()` raises `PermissionError`.
        The previous implementation caught that and returned True, which
        falsely skipped SSL on multi-bench servers (test5-bench was
        affected — install marked SSL as `[already done]` while no cert
        existed for it). Use `sudo test -f` for an authoritative answer.
        """
        cert_path = self._cert_path(ctx)
        try:
            return cert_path.exists()
        except (PermissionError, OSError):
            pass
        if not ctx.sudo_password:
            return False
        try:
            result = subprocess.run(
                ["sudo", "-S", "test", "-f", str(cert_path)],
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True,
                timeout=15,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def run(self, ctx) -> None:
        # Ensure certbot is available (bench setup lets-encrypt shells out to it).
        result = subprocess.run(["which", "certbot"], capture_output=True)
        if result.returncode != 0:
            self._sudo(
                ctx, ["apt-get", "install", "-y", "certbot", "python3-certbot-nginx"]
            )

        # Use `bench setup lets-encrypt <site>` (not raw `certbot --nginx`) so
        # bench rewrites this bench's nginx config with the SSL block and adds
        # a monthly renewal cron. Mirrors the manual runbook (Step 6.1).
        #
        # The command prompts twice; both answered 'y':
        #   1) "Running this will stop the nginx service temporarily..."
        #   2) "nginx.conf already exists and this will overwrite it..."
        bench_bin = str(Path.home() / ".local" / "bin" / "bench")
        bench_path = self._local_bin_env()["PATH"]
        self._sudo_with_stdin(
            ctx,
            [
                "env",
                f"PATH={bench_path}",
                bench_bin,
                "setup",
                "lets-encrypt",
                ctx.site_name,
            ],
            stdin=b"y\ny\n",
            cwd=str(ctx.bench_path),
        )
