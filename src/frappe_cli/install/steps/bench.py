import subprocess

from .base import InstallStep


class BenchInstallStep(InstallStep):
    name = "bench_install"
    description = "Install frappe-bench (uv)"

    def check(self, ctx) -> bool:
        try:
            result = subprocess.run(
                ["bench", "--version"],
                capture_output=True,
                text=True,
                env=self._local_bin_env(),
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def run(self, ctx) -> None:
        self._run(ctx, ["uv", "tool", "install", "frappe-bench"])
