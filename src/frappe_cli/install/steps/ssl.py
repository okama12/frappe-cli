import subprocess
from pathlib import Path

from .base import InstallStep


class SSLSetupStep(InstallStep):
    name = "ssl_setup"
    description = "Configure SSL (Let's Encrypt)"

    def _cert_path(self, ctx) -> Path:
        return Path(f"/etc/letsencrypt/live/{ctx.site_name}/fullchain.pem")

    def check(self, ctx) -> bool:
        return self._cert_path(ctx).exists()

    def run(self, ctx) -> None:
        result = subprocess.run(["which", "certbot"], capture_output=True)
        if result.returncode != 0:
            self._sudo(
                ctx, ["apt-get", "install", "-y", "certbot", "python3-certbot-nginx"]
            )
        self._sudo(
            ctx,
            [
                "certbot",
                "--nginx",
                "-d",
                ctx.site_name,
                "--non-interactive",
                "--agree-tos",
                "-m",
                ctx.ssl_email,
            ],
        )
        self._sudo(ctx, ["systemctl", "enable", "certbot.timer"])
        self._sudo(ctx, ["systemctl", "start", "certbot.timer"])
