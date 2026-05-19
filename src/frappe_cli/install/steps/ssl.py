import subprocess
from pathlib import Path

from .base import InstallStep


class SSLSetupStep(InstallStep):
    name = "ssl_setup"
    description = "Configure SSL (Let's Encrypt)"

    def _cert_path(self, ctx) -> Path:
        return Path(f"/etc/letsencrypt/live/{ctx.site_name}/fullchain.pem")

    def check(self, ctx) -> bool:
        try:
            return self._cert_path(ctx).exists()
        except PermissionError:
            # Root-owned path exists but isn't readable — cert is already installed
            return True

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
