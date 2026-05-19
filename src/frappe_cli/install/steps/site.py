import shutil

from .base import InstallStep, StepError


class SiteCreateStep(InstallStep):
    name = "site_create"
    description = "Create site"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").exists()

    def _new_site_cmd(self, ctx) -> list[str]:
        return [
            "bench",
            "new-site",
            ctx.site_name,
            "--mariadb-root-username",
            "root",
            "--mariadb-root-password",
            ctx.mariadb_root_password,
            "--admin-password",
            ctx.admin_password,
        ]

    def _log_command(self, ctx) -> None:
        if ctx.log_fn:
            ctx.log_fn(
                f"$ bench new-site {ctx.site_name} "
                "--mariadb-root-password *** --admin-password ***"
            )

    def run(self, ctx) -> None:
        cmd = self._new_site_cmd(ctx)
        cwd = str(ctx.bench_path)

        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(
                    f"[dry-run] $ bench new-site {ctx.site_name} "
                    "--mariadb-root-password *** --admin-password ***"
                )
            return

        # Stream stdout/stderr into the wizard log panel (same as other steps).
        if ctx.log_fn:
            self._log_command(ctx)
            try:
                self._popen(ctx, cmd, cwd=cwd)
            except StepError:
                raise
            return

        # Fallback when no log_fn (unit tests / programmatic use).
        import subprocess

        try:
            subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                env=self._local_bin_env(),
            )
        except subprocess.CalledProcessError as e:
            raise StepError("bench new-site failed", hint=e.stderr) from e

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
