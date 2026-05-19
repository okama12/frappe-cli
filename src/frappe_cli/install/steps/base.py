import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from frappe_cli.install.context import InstallContext


class StepError(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


class InstallStep(ABC):
    name: str
    description: str

    @abstractmethod
    def check(self, ctx: InstallContext) -> bool:
        """Return True if step is already complete and can be skipped."""
        ...

    @abstractmethod
    def run(self, ctx: InstallContext) -> None:
        """Execute the step. Raise StepError on failure."""
        ...

    def _local_bin_env(self) -> dict:
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        paths = env.get("PATH", "").split(":")
        if local_bin not in paths:
            env["PATH"] = f"{local_bin}:{env.get('PATH', '')}"
        return env

    def _sudo(self, ctx: InstallContext, cmd: list[str]) -> subprocess.CompletedProcess:
        if ctx.dry_run:
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        full_cmd = ["sudo", "-S"] + cmd
        try:
            return subprocess.run(
                full_cmd,
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                f"Command failed: {' '.join(cmd)}",
                hint=e.stderr.decode(errors="replace"),
            )

    def _sudo_write(self, ctx: InstallContext, content: str, path: str) -> None:
        """Write content to a privileged path via a temp file + sudo cp."""
        if ctx.dry_run:
            return
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp") as tmp:
            tmp.write(content)
            tmp_name = tmp.name
        try:
            subprocess.run(
                ["sudo", "-S", "cp", tmp_name, path],
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["sudo", "-S", "chmod", "644", path],
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                f"Failed to write {path}", hint=e.stderr.decode(errors="replace")
            )
        finally:
            os.unlink(tmp_name)

    def _run(
        self, ctx: InstallContext, cmd: list[str], cwd: str | None = None
    ) -> subprocess.CompletedProcess:
        """Run a command as current user (no sudo)."""
        if ctx.dry_run:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=cwd,
                env=self._local_bin_env(),
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                f"Command failed: {' '.join(cmd)}",
                hint=e.stderr,
            )
