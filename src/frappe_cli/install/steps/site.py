import shutil
import subprocess

from ..context import InstallContext
from .base import InstallStep, StepError


class SiteCreateStep(InstallStep):
    """Create the Frappe site via ``bench new-site``.

    Security note — passwords on argv:

    Earlier revisions passed both the MariaDB root password and the Frappe
    admin password as ``--mariadb-root-password`` / ``--admin-password`` flags.
    Anything on argv is world-readable through ``/proc/<pid>/cmdline``, which
    is unacceptable on a multi-user box. We now feed both passwords via
    environment variables that ``bench`` recognises:

    * ``MYSQL_PWD`` — picked up by the MariaDB client library.
    * ``FRAPPE_ADMIN_PASSWORD`` — read by ``bench new-site`` when present.

    Both vars live only in the spawned child's environment and are wiped when
    the call returns.
    """

    name = "site_create"
    description = "Create site"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").exists()

    def _new_site_cmd(self, ctx: InstallContext) -> list[str]:
        return [
            "bench",
            "new-site",
            ctx.site_name,
            "--mariadb-root-username",
            "root",
            "--no-mariadb-socket",
        ]

    def _site_env(self, ctx: InstallContext) -> dict:
        env = self._local_bin_env()
        env["MYSQL_PWD"] = ctx.mariadb_root_password
        env["FRAPPE_ADMIN_PASSWORD"] = ctx.admin_password
        return env

    def _log_command(self, ctx: InstallContext) -> None:
        if ctx.log_fn:
            ctx.log_fn(f"$ bench new-site {ctx.site_name}  (credentials via env)")

    def run(self, ctx: InstallContext) -> None:
        cmd = self._new_site_cmd(ctx)
        cwd = str(ctx.bench_path)

        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ bench new-site {ctx.site_name}")
            return

        env = self._site_env(ctx)

        if ctx.log_fn:
            self._log_command(ctx)
            self._popen_with_env(ctx, cmd, cwd=cwd, env=env)
            return

        try:
            subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            raise StepError("bench new-site failed", hint=e.stderr) from e

    def _popen_with_env(
        self, ctx: InstallContext, cmd: list[str], cwd: str, env: dict
    ) -> None:
        """Stream output to the wizard log while passing a custom env.

        Mirrors :meth:`InstallStep._popen` but accepts a pre-built environment
        so we can inject ``MYSQL_PWD`` / ``FRAPPE_ADMIN_PASSWORD`` without
        leaking them on argv.
        """
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=cwd,
        )
        captured: list[str] = []
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode(errors="replace").rstrip()
            captured.append(line)
            if ctx.log_fn and line:
                low = line.lower()
                if "[sudo]" not in low and not low.startswith("password"):
                    ctx.log_fn(line)
        proc.wait()
        if proc.returncode != 0:
            raise StepError(
                "bench new-site failed",
                hint="\n".join(captured[-10:]),
            )

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
