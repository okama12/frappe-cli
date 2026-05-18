import os
import subprocess

from .base import InstallStep, StepError


class SiteCreateStep(InstallStep):
    name = "site_create"
    description = "Create site"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").exists()

    def run(self, ctx) -> None:
        if ctx.dry_run:
            return
        env = os.environ.copy()
        env["MARIADB_ROOT_PASSWORD"] = ctx.mariadb_root_password
        env["ADMIN_PASSWORD"] = ctx.admin_password
        try:
            subprocess.run(
                [
                    "bench",
                    "new-site",
                    ctx.site_name,
                    "--mariadb-root-username",
                    "root",
                    "--mariadb-root-password-from-env",
                    "--admin-password-from-env",
                ],
                cwd=str(ctx.bench_path),
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            raise StepError("bench new-site failed", hint=e.stderr)
