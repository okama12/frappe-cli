import shutil
import subprocess

from .base import InstallStep, StepError


class SiteCreateStep(InstallStep):
    name = "site_create"
    description = "Create site"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").exists()

    def run(self, ctx) -> None:
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(
                    f"[dry-run] $ bench new-site {ctx.site_name} --mariadb-root-password *** --admin-password ***"
                )
            return
        try:
            subprocess.run(
                [
                    "bench",
                    "new-site",
                    ctx.site_name,
                    "--mariadb-root-username",
                    "root",
                    "--mariadb-root-password",
                    ctx.mariadb_root_password,
                    "--admin-password",
                    ctx.admin_password,
                ],
                cwd=str(ctx.bench_path),
                capture_output=True,
                text=True,
                check=True,
                env=self._local_bin_env(),
            )
        except subprocess.CalledProcessError as e:
            raise StepError("bench new-site failed", hint=e.stderr)

    def rollback(self, ctx) -> None:
        site_path = ctx.bench_path / "sites" / ctx.site_name
        if site_path.exists():
            if ctx.log_fn:
                ctx.log_fn(f"Rolling back: removing site files at {site_path}")
            shutil.rmtree(site_path, ignore_errors=True)
        if ctx.log_fn:
            ctx.log_fn(
                f"Note: MariaDB database '{ctx.site_name}' may need manual cleanup: "
                f'mysql -u root -e "DROP DATABASE IF EXISTS `{ctx.site_name}`;"'
            )
