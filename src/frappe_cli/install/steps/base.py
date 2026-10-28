import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path

from frappe_cli.install.context import InstallContext


class StepError(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


def sudo_prefix(password):
    """Authenticate separately so cached/NOPASSWD sudo cannot consume payloads."""
    if os.geteuid() == 0:
        return []
    try:
        subprocess.run(
            ["sudo", "-S", "-p", "", "-v"],
            input=(password + "\n").encode(),
            capture_output=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        raise StepError(
            "Sudo authentication failed.",
            hint="Check your password and sudo permissions, then resume.",
        ) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StepError(
            "Sudo authentication could not complete.",
            hint="Check that sudo is installed and available, then retry.",
        ) from exc
    return ["sudo", "-n"]


def privileged_command(password, command):
    prefix = sudo_prefix(password)
    if command[0] in {"apt", "apt-get"}:
        return [*prefix, "env", "DEBIAN_FRONTEND=noninteractive", *command]
    return [*prefix, *command]


def consume_process(ctx, proc, cmd, input_bytes=None):
    """Stream a bounded log tail and stop the child when the operator cancels."""
    captured: deque[str] = deque(maxlen=100)
    try:
        if input_bytes:
            assert proc.stdin is not None
            proc.stdin.write(input_bytes)
            proc.stdin.close()
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode(errors="replace").rstrip()
            captured.append(line)
            if ctx.log_fn and line:
                low = line.lower()
                if "[sudo]" not in low and not low.startswith("password"):
                    ctx.log_fn(line)
        proc.wait()
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        raise
    if proc.returncode != 0:
        raise StepError(
            f"Command failed: {' '.join(cmd[:3])}", hint="\n".join(list(captured)[-10:])
        )
    return subprocess.CompletedProcess(cmd, proc.returncode, b"", b"")


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
        return consume_process(ctx, proc, cmd, input_bytes)

    def _sudo(
        self, ctx: InstallContext, cmd: list[str], cwd: str | None = None
    ) -> subprocess.CompletedProcess:
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ sudo {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        full_cmd = privileged_command(ctx.sudo_password, cmd)
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
            return self._popen(ctx, full_cmd, cwd=cwd)
        try:
            return subprocess.run(
                full_cmd,
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
        """Like :meth:`_sudo` but pipes bytes exclusively to the command's stdin.

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
        full_cmd = privileged_command(ctx.sudo_password, cmd)
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
        try:
            return subprocess.run(
                full_cmd,
                input=stdin_after_password,
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
        """Authenticate sudo, then send scripted answers directly to the child.

        Used for commands like `bench setup lets-encrypt <site>` that prompt
        interactively (e.g. "stop nginx? [y/N]", "overwrite nginx.conf? [y/N]").
        Authentication uses a separate process so cached sudo never shifts answers.
        """
        if ctx.dry_run:
            if ctx.log_fn:
                ctx.log_fn(f"[dry-run] $ sudo {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        full_cmd = privileged_command(ctx.sudo_password, cmd)
        if ctx.log_fn:
            ctx.log_fn(f"$ {' '.join(cmd)}")
        return self._popen(ctx, full_cmd, input_bytes=stdin, cwd=cwd)

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
            prefix = sudo_prefix(ctx.sudo_password)
            subprocess.run(
                [*prefix, "cp", tmp_name, path],
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [*prefix, "chmod", "644", path],
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
