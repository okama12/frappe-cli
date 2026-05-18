import subprocess
from typing import List

from .base import InstallStep

SYSTEM_PACKAGES: List[str] = [
    "python3-dev",
    "python3-setuptools",
    "python3-pip",
    "python3-venv",
    "git",
    "build-essential",
    "libssl-dev",
    "libffi-dev",
    "curl",
    "software-properties-common",
    "xvfb",
    "libfontconfig",
]


class SystemUpdateStep(InstallStep):
    name = "system_update"
    description = "System update & upgrade"

    def check(self, ctx) -> bool:
        return False

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "update", "-y"])
        self._sudo(
            ctx, ["apt-get", "upgrade", "-y", "-o", "Dpkg::Options::=--force-confdef"]
        )


class SystemDepsStep(InstallStep):
    name = "system_deps"
    description = "Install system dependencies"

    def check(self, ctx) -> bool:
        for pkg in SYSTEM_PACKAGES:
            result = subprocess.run(["dpkg", "-l", pkg], capture_output=True, text=True)
            if result.returncode != 0:
                return False
        return True

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "install", "-y"] + SYSTEM_PACKAGES)
