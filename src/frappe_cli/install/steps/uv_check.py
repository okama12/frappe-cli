import os
import subprocess
from pathlib import Path

from .base import InstallStep, StepError


class UvCheckStep(InstallStep):
    name = "uv_check"
    description = "Verify uv"

    def check(self, ctx) -> bool:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def run(self, ctx) -> None:
        if ctx.dry_run:
            return
        try:
            script = subprocess.run(
                ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
                capture_output=True,
                check=True,
            )
            subprocess.run(["sh"], input=script.stdout, check=True)
        except subprocess.CalledProcessError as e:
            raise StepError("Failed to install uv", hint=str(e))

        local_bin = str(Path.home() / ".local" / "bin")
        current = os.environ.get("PATH", "")
        if local_bin not in current:
            os.environ["PATH"] = f"{local_bin}:{current}"
