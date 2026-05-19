import subprocess
from pathlib import Path

from .base import InstallStep


class BenchInstallStep(InstallStep):
    name = "bench_install"
    description = "Install frappe-bench (uv)"

    # Common install locations bench may live in on a non-fresh VPS:
    # - ~/.local/bin/bench   (uv tool install — what this wizard uses)
    # - /usr/local/bin/bench (pip install --user, or symlink)
    # - /usr/bin/bench       (distro package — rare)
    _CANDIDATE_PATHS = (
        Path.home() / ".local" / "bin" / "bench",
        Path("/usr/local/bin/bench"),
        Path("/usr/bin/bench"),
    )

    def check(self, ctx) -> bool:
        """Skip install if bench is already available.

        Works on non-fresh VPS that already has bench (installed via pip,
        uv, or distro package) and may have one or more benches under
        the user's home. Logs the detected version and existing benches
        so the wizard's renderer makes the state visible.
        """
        version = self._detect_bench_version()
        if version is None:
            return False
        if ctx.log_fn:
            ctx.log_fn(f"Found existing bench: {version}")
            self._log_existing_benches(ctx)
        return True

    def run(self, ctx) -> None:
        self._run(ctx, ["uv", "tool", "install", "frappe-bench"])

    def _detect_bench_version(self) -> str | None:
        """Return bench version string if installed, else None.

        Tries `bench --version` from PATH first, then falls back to
        explicit candidate paths so the check still passes when sudo
        environments or shells have a stripped PATH.
        """
        try:
            result = subprocess.run(
                ["bench", "--version"],
                capture_output=True,
                text=True,
                env=self._local_bin_env(),
            )
            if result.returncode == 0:
                return (result.stdout or result.stderr).strip() or "unknown"
        except FileNotFoundError:
            pass

        for candidate in self._CANDIDATE_PATHS:
            if candidate.exists():
                try:
                    result = subprocess.run(
                        [str(candidate), "--version"],
                        capture_output=True,
                        text=True,
                        env=self._local_bin_env(),
                    )
                    if result.returncode == 0:
                        return (
                            result.stdout or result.stderr
                        ).strip() + f" ({candidate})"
                except (OSError, subprocess.SubprocessError):
                    continue
        return None

    def _log_existing_benches(self, ctx) -> None:
        """List existing benches under the user's home so the user knows
        the wizard is sharing the host with prior installs."""
        home = Path.home()
        if not home.exists():
            return
        existing: list[str] = []
        try:
            children = list(home.iterdir())
        except (OSError, PermissionError):
            return
        for child in children:
            try:
                if (
                    child.is_dir()
                    and (child / "apps" / "frappe").exists()
                    and (child / "sites").exists()
                ):
                    existing.append(child.name)
            except (OSError, PermissionError):
                continue
        if existing and ctx.log_fn:
            ctx.log_fn(f"Existing benches under {home}: {', '.join(sorted(existing))}")
