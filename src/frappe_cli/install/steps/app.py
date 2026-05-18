import subprocess

from .base import InstallStep


class AppGetStep(InstallStep):
    name = "app_get"
    description = "Get app from GitHub"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "apps" / ctx.app_name).exists()

    def run(self, ctx) -> None:
        self._run(
            ctx,
            [
                "bench",
                "get-app",
                ctx.app_url,
                "--branch",
                ctx.app_branch,
            ],
            cwd=str(ctx.bench_path),
        )


class AppInstallStep(InstallStep):
    name = "app_install"
    description = "Install app on site"

    def check(self, ctx) -> bool:
        result = subprocess.run(
            ["bench", "--site", ctx.site_name, "list-apps"],
            capture_output=True,
            text=True,
            cwd=str(ctx.bench_path),
        )
        return ctx.app_name in result.stdout

    def run(self, ctx) -> None:
        self._run(
            ctx,
            [
                "bench",
                "--site",
                ctx.site_name,
                "install-app",
                ctx.app_name,
            ],
            cwd=str(ctx.bench_path),
        )
