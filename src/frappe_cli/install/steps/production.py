import getpass
import os
import subprocess
import tempfile
from pathlib import Path

from .base import InstallStep, StepError


class ProductionSetupStep(InstallStep):
    name = "production_setup"
    description = "Setup production (nginx + supervisor)"

    def check(self, ctx) -> bool:
        bench_conf = Path(f"/etc/nginx/conf.d/{ctx.bench_name}.conf")
        return bench_conf.exists()

    def run(self, ctx) -> None:
        if ctx.dry_run:
            return
        current_user = getpass.getuser()
        askpass = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
        try:
            askpass.write(f"#!/bin/sh\necho '{ctx.sudo_password}'\n")
            askpass.close()
            os.chmod(askpass.name, 0o700)
            env = os.environ.copy()
            env["SUDO_ASKPASS"] = askpass.name
            result = subprocess.run(
                ["bench", "setup", "production", current_user, "--yes"],
                cwd=str(ctx.bench_path),
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                raise StepError("bench setup production failed", hint=result.stderr)
        finally:
            os.unlink(askpass.name)
