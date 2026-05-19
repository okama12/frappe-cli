import subprocess

from .base import InstallStep


class AppGetStep(InstallStep):
    name = "app_get"
    description = "Get app from GitHub"

    def check(self, ctx) -> bool:
        if not ctx.app_url:
            return True
        return (ctx.bench_path / "apps" / ctx.app_name).exists()

    def run(self, ctx) -> None:
        if not ctx.app_url:
            return
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
        if not ctx.app_url:
            return True
        try:
            result = subprocess.run(
                ["bench", "--site", ctx.site_name, "list-apps"],
                capture_output=True,
                text=True,
                cwd=str(ctx.bench_path),
                env=self._local_bin_env(),
            )
            return ctx.app_name in result.stdout.splitlines()
        except FileNotFoundError:
            return False

    def run(self, ctx) -> None:
        if not ctx.app_url:
            return
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
