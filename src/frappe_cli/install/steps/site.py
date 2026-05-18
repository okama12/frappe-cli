from .base import InstallStep


class SiteCreateStep(InstallStep):
    name = "site_create"
    description = "Create site"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").exists()

    def run(self, ctx) -> None:
        self._run(
            ctx,
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
        )
