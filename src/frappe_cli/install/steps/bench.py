import subprocess

from .base import InstallStep


class BenchInstallStep(InstallStep):
    name = "bench_install"
    description = "Install frappe-bench (uv)"

    def check(self, ctx) -> bool:
        result = subprocess.run(["bench", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def run(self, ctx) -> None:
        self._run(ctx, ["uv", "tool", "install", "frappe-bench"])
