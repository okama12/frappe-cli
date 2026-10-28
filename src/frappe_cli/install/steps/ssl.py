import subprocess
from pathlib import Path

from .base import InstallStep


class LogConsole:
    def __init__(self, log_fn):
        self.log_fn = log_fn

    def print(self, value, **kwargs):
        self.log_fn(str(value))


class SSLSetupStep(InstallStep):
    name = "ssl_setup"
    description = "Configure SSL (Let's Encrypt)"

    def _cert_path(self, ctx) -> Path:
        return Path(f"/etc/letsencrypt/live/{ctx.site_name}/fullchain.pem")

    def check(self, ctx) -> bool:
        """Return True only if a cert already exists for THIS site.

        `/etc/letsencrypt/live/` is mode 700 root-owned as soon as any cert
        is issued, so a non-root `Path.exists()` raises `PermissionError`.
        The previous implementation caught that and returned True, which
        falsely skipped SSL on multi-bench servers (test5-bench was
        affected — install marked SSL as `[already done]` while no cert
        existed for it). Use `sudo test -f` for an authoritative answer.
        """
        cert_path = self._cert_path(ctx)
        present = False
        try:
            present = cert_path.exists()
        except (PermissionError, OSError):
            pass
        if not present and ctx.sudo_password:
            try:
                result = subprocess.run(
                    ["sudo", "-S", "test", "-f", str(cert_path)],
                    input=(ctx.sudo_password + "\n").encode(),
                    capture_output=True,
                    timeout=15,
                )
                present = result.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                return False
        if present:
            import click

            from frappe_cli.ssl.secure import Runner, certificate_valid, verify_https

            try:
                if certificate_valid(ctx.site_name, Runner(ctx.sudo_password)):
                    verify_https(ctx.site_name)
                    return True
            except click.ClickException:
                pass
        return False

    def run(self, ctx) -> None:
        import click
        from rich.console import Console

        from frappe_cli.ssl.secure import configure_https

        from .base import StepError

        output = LogConsole(ctx.log_fn) if ctx.log_fn else Console()
        try:
            configure_https(
                ctx.site_name,
                email=ctx.ssl_email,
                bench=ctx.bench_path,
                dry_run=ctx.dry_run,
                sudo_password=ctx.sudo_password,
                console=output,
            )
        except click.ClickException as exc:
            raise StepError("HTTPS setup failed", hint=exc.format_message()) from exc
