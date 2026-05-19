import subprocess

from .base import InstallStep, StepError


class NodeJSStep(InstallStep):
    name = "nodejs"
    description = "Install Node.js + Yarn"

    def check(self, ctx) -> bool:
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def run(self, ctx) -> None:
        if ctx.dry_run:
            return
        node_version = "18" if ctx.ubuntu_version == "22.04" else "20"
        try:
            script = subprocess.run(
                ["curl", "-fsSL", f"https://deb.nodesource.com/setup_{node_version}.x"],
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["sudo", "-S", "bash"],
                input=(ctx.sudo_password + "\n").encode() + script.stdout,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                "Failed to run NodeSource setup script",
                hint=e.stderr.decode(errors="replace"),
            )
        self._sudo(ctx, ["apt-get", "install", "-y", "nodejs"])
        self._sudo(ctx, ["npm", "install", "-g", "yarn"])
