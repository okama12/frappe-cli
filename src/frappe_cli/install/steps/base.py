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

    def rollback(self, ctx: InstallContext) -> None:  # noqa: B027
        """Best-effort cleanup called when this step fails. Override in subclasses."""

    def _local_bin_env(self) -> dict:
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        paths = env.get("PATH", "").split(":")
        if local_bin not in paths:
            env["PATH"] = f"{local_bin}:{env.get('PATH', '')}"
        env["PYTHONUNBUFFERED"] = "1"
        # Prevent apt/dpkg from showing interactive prompts in a non-TTY
        # subprocess. Without this, packages like software-properties-common
        # hang forever waiting for input on Ubuntu 24.04.
        env["DEBIAN_FRONTEND"] = "noninteractive"
        return env

    def _popen(
        self,
        ctx: InstallContext,
        cmd: list[str],
        input_bytes: bytes | None = None,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Run cmd via Popen, streaming output to ctx.log_fn line by line."""
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_bytes else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=self._local_bin_env(),
            cwd=cwd,
        )
        if input_bytes:
            assert proc.stdin is not None
            proc.stdin.write(input_bytes)
            proc.stdin.close()

        captured: list[str] = []
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode(errors="replace").rstrip()
            captured.append(line)
            if ctx.log_fn and line:
                # Filter sudo password prompts
                low = line.lower()
                if "[sudo]" not in low and not low.startswith("password"):
                    ctx.log_fn(line)

        proc.wait()
        if proc.returncode != 0:
            hint = "\n".join(captured[-10:])
            raise StepError(
                f"Command failed: {' '.join(cmd[:3])}",
                hint=hint,
            )
        return subprocess.CompletedProcess(cmd, proc.returncode, b"", b"")

    def _sudo(
        self, ctx: InstallContext, cmd: list[str], cwd: str | None = None
    ) -> subprocess.CompletedProcess:
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ sudo {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        input_bytes = (ctx.sudo_password + "\n").encode()
        full_cmd = ["sudo", "-S"] + cmd
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
            return self._popen(ctx, full_cmd, input_bytes=input_bytes, cwd=cwd)
        try:
            return subprocess.run(
                full_cmd,
                input=input_bytes,
                capture_output=True,
                check=True,
                cwd=cwd,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                f"Command failed: {' '.join(cmd)}",
                hint=e.stderr.decode(errors="replace"),
            )

    def _sudo_pipe_stdin(
        self,
        ctx: InstallContext,
        cmd: list[str],
        stdin_after_password: bytes,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Like :meth:`_sudo` but pipes additional bytes to the command's stdin.

        Unlike :meth:`_sudo_with_stdin` (which streams output through Popen),
        this captures output. It is used by ``MariaDBSecureStep`` so the SQL
        body is fed via stdin instead of via ``-e`` on argv — keeping
        passwords out of ``/proc/<pid>/cmdline`` and avoiding shell/SQL
        interpolation issues entirely.
        """
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ sudo {' '.join(cmd)}  < (stdin)")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        full_cmd = ["sudo", "-S"] + cmd
        input_bytes = (ctx.sudo_password + "\n").encode() + stdin_after_password
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
        try:
            return subprocess.run(
                full_cmd,
                input=input_bytes,
                capture_output=True,
                check=True,
                cwd=cwd,
            )
        except subprocess.CalledProcessError as e:
            raise StepError(
                f"Command failed: {' '.join(cmd)}",
                hint=e.stderr.decode(errors="replace"),
            )

    def _sudo_with_stdin(
        self,
        ctx: InstallContext,
        cmd: list[str],
        stdin: bytes,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a sudo command and feed extra bytes on stdin AFTER the sudo password.

        Used for commands like `bench setup lets-encrypt <site>` that prompt
        interactively (e.g. "stop nginx? [y/N]", "overwrite nginx.conf? [y/N]").
        We send the sudo password first, then the scripted answers.
        """
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ sudo {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        full_cmd = ["sudo", "-S"] + cmd
        input_bytes = (ctx.sudo_password + "\n").encode() + stdin
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
        return self._popen(ctx, full_cmd, input_bytes=input_bytes, cwd=cwd)

    def _sudo_write(self, ctx: InstallContext, content: str, path: str) -> None:
        """Write content to a privileged path via a temp file + sudo cp."""
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] write {path}")
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
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
            return self._popen(ctx, cmd, cwd=cwd)
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
