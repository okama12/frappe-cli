import shutil
import subprocess

from ..context import InstallContext
from .base import InstallStep, StepError


class SiteCreateStep(InstallStep):
    """Create the Frappe site via ``bench new-site``.

    Security note — passwords on argv:

    Passwords are never passed on argv (world-readable via /proc/<pid>/cmdline).
    ``MYSQL_PWD`` feeds the MariaDB root password via the client library env var.
    The Frappe admin password is piped to stdin because ``FRAPPE_ADMIN_PASSWORD``
    is not reliably honoured by all installed bench/frappe versions.
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
            "--mariadb-user-host-login-scope=%",
            "--force",
        ]

    def _site_env(self, ctx: InstallContext) -> dict:
        env = self._local_bin_env()
        env["MYSQL_PWD"] = ctx.mariadb_root_password
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
        # bench prompts: (1) MySQL root password, (2) admin password, (3) re-enter admin.
        # All three are piped via stdin; start_new_session forces getpass to read stdin.
        input_bytes = (
            f"{ctx.mariadb_root_password}\n"
            f"{ctx.admin_password}\n"
            f"{ctx.admin_password}\n"
        ).encode()

        if ctx.log_fn:
            self._log_command(ctx)
            self._popen_with_env(ctx, cmd, cwd=cwd, env=env, input_bytes=input_bytes)
            return

        try:
            subprocess.run(
                cmd,
                input=input_bytes,
                cwd=cwd,
                capture_output=True,
                check=True,
                env=env,
                start_new_session=True,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                "bench new-site failed", hint=e.stderr.decode(errors="replace")
            ) from e

    def _popen_with_env(
        self,
        ctx: InstallContext,
        cmd: list[str],
        cwd: str,
        env: dict,
        input_bytes: bytes | None = None,
    ) -> None:
        """Stream output to the wizard log while passing a custom env.

        Mirrors :meth:`InstallStep._popen` but accepts a pre-built environment
        so we can inject ``MYSQL_PWD`` without leaking it on argv, and
        optionally pipe ``input_bytes`` to stdin (used to supply the admin
        password when bench prompts interactively).
        """
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_bytes else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=cwd,
            start_new_session=True,
        )
        if input_bytes and proc.stdin:
            proc.stdin.write(input_bytes)
            proc.stdin.close()
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
