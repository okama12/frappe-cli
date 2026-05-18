import subprocess

from .base import InstallStep


class WkhtmltopdfStep(InstallStep):
    name = "wkhtmltopdf"
    description = "Install wkhtmltopdf"

    def check(self, ctx) -> bool:
        result = subprocess.run(
            ["wkhtmltopdf", "--version"], capture_output=True, text=True
        )
        return result.returncode == 0

    def run(self, ctx) -> None:
        packages = [
            "wkhtmltopdf",
            "libxrender1",
            "xfonts-75dpi",
            "xfonts-base",
            "fontconfig",
        ]
        self._sudo(ctx, ["apt-get", "install", "-y"] + packages)
