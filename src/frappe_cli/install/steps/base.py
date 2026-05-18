from abc import ABC, abstractmethod
from typing import List
import subprocess


class StepError(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


class InstallStep(ABC):
    name: str
    description: str

    @abstractmethod
    def check(self, ctx) -> bool:
        """Return True if step is already complete and can be skipped."""
        ...

    @abstractmethod
    def run(self, ctx) -> None:
        """Execute the step. Raise StepError on failure."""
        ...

    def _sudo(self, ctx, cmd: List[str]) -> subprocess.CompletedProcess:
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

    def _sudo_write(self, ctx, content: str, path: str) -> None:
        """Write content to a privileged path via a temp file + sudo cp."""
        if ctx.dry_run:
            return
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp")
        try:
            tmp.write(content)
            tmp.close()
            subprocess.run(
                ["sudo", "-S", "cp", tmp.name, path],
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True, check=True,
            )
            subprocess.run(
                ["sudo", "-S", "chmod", "644", path],
                input=(ctx.sudo_password + "\n").encode(),
                capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(f"Failed to write {path}", hint=e.stderr.decode(errors="replace"))
        finally:
            os.unlink(tmp.name)

    def _run(self, ctx, cmd: List[str], cwd: str = None) -> subprocess.CompletedProcess:
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
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                f"Command failed: {' '.join(cmd)}",
                hint=e.stderr,
            )
