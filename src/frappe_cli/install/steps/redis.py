import subprocess

from .base import InstallStep


class RedisStep(InstallStep):
    name = "redis"
    description = "Install Redis"

    def check(self, ctx) -> bool:
        result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
        return result.returncode == 0 and "PONG" in result.stdout

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "install", "-y", "redis-server"])
        self._sudo(ctx, ["systemctl", "enable", "redis-server"])
        self._sudo(ctx, ["systemctl", "start", "redis-server"])
