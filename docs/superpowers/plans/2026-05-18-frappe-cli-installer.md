# frappe-cli Production Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a `frappe install` wizard command that automates end-to-end production Frappe deployment on Ubuntu 22.04/24.04 VPS — collecting all credentials upfront then running 15 idempotent steps with a live Rich UI and `--resume` support.

**Architecture:** Option A from design — keep existing module layout, gut duplicated internals, add `ui/` layer for shared Rich components, add `install/steps/` for one-file-per-step implementations, add `install/wizard.py` as the orchestrator. All steps share a single `InstallContext` dataclass; no globals.

**Tech Stack:** Python 3.10+, Click 8, Rich 13, uv (tool install), frappe-bench, certbot. Tests use `pytest` + `unittest.mock` + `click.testing.CliRunner`. Run tests with `PYTHONPATH=src poetry run pytest`.

---

## File Map

**New files (create):**
- `src/frappe_cli/install/context.py` — `InstallContext` dataclass
- `src/frappe_cli/install/state.py` — `InstallState` + save/load/clear
- `src/frappe_cli/install/steps/__init__.py` — `ALL_STEPS` ordered list
- `src/frappe_cli/install/steps/base.py` — `InstallStep` ABC + `StepError`
- `src/frappe_cli/install/steps/system.py` — `SystemUpdateStep`, `SystemDepsStep`
- `src/frappe_cli/install/steps/uv_check.py` — `UvCheckStep`
- `src/frappe_cli/install/steps/nodejs.py` — `NodeJSStep`
- `src/frappe_cli/install/steps/mariadb.py` — `MariaDBInstallStep`, `MariaDBSecureStep`
- `src/frappe_cli/install/steps/redis.py` — `RedisStep`
- `src/frappe_cli/install/steps/wkhtmltopdf.py` — `WkhtmltopdfStep`
- `src/frappe_cli/install/steps/bench.py` — `BenchInstallStep`
- `src/frappe_cli/install/steps/init_bench.py` — `BenchInitStep`
- `src/frappe_cli/install/steps/site.py` — `SiteCreateStep`
- `src/frappe_cli/install/steps/app.py` — `AppGetStep`, `AppInstallStep`
- `src/frappe_cli/install/steps/production.py` — `ProductionSetupStep`
- `src/frappe_cli/install/steps/ssl.py` — `SSLSetupStep`
- `src/frappe_cli/install/wizard.py` — `wizard` Click command (orchestrator)
- `src/frappe_cli/ui/__init__.py`
- `src/frappe_cli/ui/panels.py` — `print_header`, `print_success`, `print_error`
- `src/frappe_cli/ui/steps.py` — `StepListRenderer`, `StepStatus`
- `src/frappe_cli/ui/prompts.py` — `collect_inputs`, `collect_credentials_for_resume`
- `tests/test_install_context.py`
- `tests/test_install_state.py`
- `tests/test_install_steps.py`
- `tests/test_install_wizard.py`
- `tests/test_ui_steps.py`

**Modify (existing files):**
- `src/frappe_cli/install/__init__.py` — add `wizard` command
- All modules with duplicate `RichShell`/`setup_logger` — replace with shared utils (Task 15)

---

## Task 1: InstallContext + Step base class

**Files:**
- Create: `src/frappe_cli/install/context.py`
- Create: `src/frappe_cli/install/steps/base.py`
- Create: `tests/test_install_context.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_install_context.py
from frappe_cli.install.context import InstallContext
from pathlib import Path


def make_ctx(**overrides):
    defaults = dict(
        bench_name="frappe-bench",
        site_name="mysite.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15",
        sudo_password="secret",
        mariadb_root_password="dbpass",
        admin_password="adminpass",
        ssl_email="admin@mysite.com",
        ubuntu_version="22.04",
        dry_run=False,
        debug=False,
    )
    defaults.update(overrides)
    return InstallContext(**defaults)


def test_app_name_from_plain_url():
    ctx = make_ctx(app_url="https://github.com/frappe/erpnext")
    assert ctx.app_name == "erpnext"


def test_app_name_strips_git_suffix():
    ctx = make_ctx(app_url="https://github.com/frappe/erpnext.git")
    assert ctx.app_name == "erpnext"


def test_app_name_custom_app():
    ctx = make_ctx(app_url="https://github.com/myorg/my_custom_app.git")
    assert ctx.app_name == "my_custom_app"


def test_bench_path_is_under_home():
    ctx = make_ctx(bench_name="frappe-bench")
    assert ctx.bench_path == Path.home() / "frappe-bench"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_context.py -v
```

Expected: `ModuleNotFoundError: No module named 'frappe_cli.install.context'`

- [ ] **Step 3: Create `src/frappe_cli/install/context.py`**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallContext:
    bench_name: str
    site_name: str
    frappe_branch: str
    app_url: str
    app_branch: str
    sudo_password: str
    mariadb_root_password: str
    admin_password: str
    ssl_email: str
    ubuntu_version: str
    dry_run: bool
    debug: bool = False

    @property
    def app_name(self) -> str:
        return self.app_url.rstrip("/").split("/")[-1].removesuffix(".git")

    @property
    def bench_path(self) -> Path:
        return Path.home() / self.bench_name
```

- [ ] **Step 4: Create `src/frappe_cli/install/steps/base.py`**

```python
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
```

- [ ] **Step 5: Create `src/frappe_cli/install/steps/__init__.py`** (empty for now)

```python
# populated in Task 12
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_context.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add src/frappe_cli/install/context.py src/frappe_cli/install/steps/base.py \
        src/frappe_cli/install/steps/__init__.py tests/test_install_context.py
git commit -m "feat: add InstallContext dataclass and InstallStep base class"
```

---

## Task 2: Resume state manager

**Files:**
- Create: `src/frappe_cli/install/state.py`
- Create: `tests/test_install_state.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_install_state.py
import json
from pathlib import Path
import pytest
from unittest.mock import patch
from frappe_cli.install.state import (
    InstallState, save_state, load_state, clear_state, state_exists, STATE_FILE
)


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    fake_state = tmp_path / ".frappe-cli-state.json"
    monkeypatch.setattr("frappe_cli.install.state.STATE_FILE", fake_state)
    yield fake_state
    if fake_state.exists():
        fake_state.unlink()


def test_state_does_not_exist_initially(clean_state):
    assert not state_exists()


def test_save_and_load_roundtrip(clean_state):
    state = InstallState(
        bench_name="frappe-bench",
        site_name="mysite.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15",
        ssl_email="admin@mysite.com",
        ubuntu_version="22.04",
        completed_steps=["system_update", "system_deps"],
    )
    save_state(state)
    loaded = load_state()
    assert loaded.bench_name == "frappe-bench"
    assert loaded.completed_steps == ["system_update", "system_deps"]


def test_save_creates_file(clean_state):
    save_state(InstallState(bench_name="b", site_name="s.com", frappe_branch="v15",
                            app_url="u", app_branch="v15", ssl_email="e@e.com",
                            ubuntu_version="22.04", completed_steps=[]))
    assert state_exists()


def test_clear_removes_file(clean_state):
    save_state(InstallState(bench_name="b", site_name="s.com", frappe_branch="v15",
                            app_url="u", app_branch="v15", ssl_email="e@e.com",
                            ubuntu_version="22.04", completed_steps=[]))
    clear_state()
    assert not state_exists()


def test_passwords_not_in_state(clean_state):
    state = InstallState(bench_name="b", site_name="s.com", frappe_branch="v15",
                         app_url="u", app_branch="v15", ssl_email="e@e.com",
                         ubuntu_version="22.04", completed_steps=[])
    save_state(state)
    raw = clean_state.read_text()
    assert "sudo_password" not in raw
    assert "mariadb_root_password" not in raw
    assert "admin_password" not in raw
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'frappe_cli.install.state'`

- [ ] **Step 3: Create `src/frappe_cli/install/state.py`**

```python
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List

STATE_FILE = Path.home() / ".frappe-cli-state.json"


@dataclass
class InstallState:
    bench_name: str = ""
    site_name: str = ""
    frappe_branch: str = ""
    app_url: str = ""
    app_branch: str = ""
    ssl_email: str = ""
    ubuntu_version: str = ""
    completed_steps: List[str] = field(default_factory=list)


def save_state(state: InstallState) -> None:
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2))


def load_state() -> InstallState:
    if not STATE_FILE.exists():
        return InstallState()
    data = json.loads(STATE_FILE.read_text())
    return InstallState(**data)


def clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def state_exists() -> bool:
    return STATE_FILE.exists()
```

- [ ] **Step 4: Run to verify pass**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_state.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/frappe_cli/install/state.py tests/test_install_state.py
git commit -m "feat: add InstallState resume state manager"
```

---

## Task 3: UI layer — panels, step renderer, prompts

**Files:**
- Create: `src/frappe_cli/ui/__init__.py`
- Create: `src/frappe_cli/ui/panels.py`
- Create: `src/frappe_cli/ui/steps.py`
- Create: `src/frappe_cli/ui/prompts.py`
- Create: `tests/test_ui_steps.py`

- [ ] **Step 1: Write failing tests for StepListRenderer**

```python
# tests/test_ui_steps.py
from frappe_cli.ui.steps import StepListRenderer, StepStatus


def test_initial_state_all_pending():
    r = StepListRenderer(["Step A", "Step B"])
    rendered = r.render()
    assert "○" in str(rendered)


def test_mark_running():
    r = StepListRenderer(["Step A"])
    r.mark_running("Step A")
    assert r._steps[0].status == StepStatus.RUNNING


def test_mark_done():
    r = StepListRenderer(["Step A"])
    r.mark_done("Step A")
    assert r._steps[0].status == StepStatus.DONE


def test_mark_skipped():
    r = StepListRenderer(["Step A"])
    r.mark_skipped("Step A")
    assert r._steps[0].status == StepStatus.SKIPPED


def test_mark_failed():
    r = StepListRenderer(["Step A"])
    r.mark_failed("Step A")
    assert r._steps[0].status == StepStatus.FAILED


def test_unknown_step_name_ignored():
    r = StepListRenderer(["Step A"])
    r.mark_done("Nonexistent")  # should not raise
    assert r._steps[0].status == StepStatus.PENDING
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_ui_steps.py -v
```

Expected: `ModuleNotFoundError: No module named 'frappe_cli.ui'`

- [ ] **Step 3: Create `src/frappe_cli/ui/__init__.py`** (empty)

```python
```

- [ ] **Step 4: Create `src/frappe_cli/ui/steps.py`**

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from rich.text import Text


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepDisplay:
    name: str
    status: StepStatus = StepStatus.PENDING
    elapsed: float = 0.0


class StepListRenderer:
    def __init__(self, step_names: List[str]):
        self._steps = [StepDisplay(name=s) for s in step_names]

    def render(self) -> Text:
        text = Text()
        text.append("\n ─── Installing Frappe Production Stack ──────────────\n\n")
        for step in self._steps:
            if step.status == StepStatus.DONE:
                text.append(f"   ✓  {step.name}\n", style="green")
            elif step.status == StepStatus.SKIPPED:
                text.append(f"   ✓  {step.name} ", style="dim green")
                text.append("[already done]\n", style="dim")
            elif step.status == StepStatus.RUNNING:
                text.append(f"   ⠸  {step.name}...", style="cyan")
                if step.elapsed > 0:
                    text.append(f"    [{step.elapsed:.0f}s]\n", style="dim")
                else:
                    text.append("\n")
            elif step.status == StepStatus.FAILED:
                text.append(f"   ✗  {step.name}\n", style="bold red")
            else:
                text.append(f"   ○  {step.name}\n", style="dim")
        return text

    def _find(self, name: str) -> StepDisplay | None:
        return next((s for s in self._steps if s.name == name), None)

    def mark_running(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.RUNNING

    def mark_done(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.DONE

    def mark_skipped(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.SKIPPED

    def mark_failed(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.FAILED

    def update_elapsed(self, name: str, elapsed: float) -> None:
        s = self._find(name)
        if s:
            s.elapsed = elapsed
```

- [ ] **Step 5: Create `src/frappe_cli/ui/panels.py`**

```python
import importlib.metadata

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def print_header(console: Console) -> None:
    version = importlib.metadata.version("frappe-cli")
    content = Text()
    content.append("  Frappe CLI  ", style="bold green")
    content.append(f"v{version}\n", style="bold")
    content.append("  Production Server Installer", style="dim")
    console.print(Panel(content, box=box.ROUNDED, padding=(1, 2)))


def print_success(console: Console, ctx) -> None:
    lines = "\n".join([
        f"[bold green]✓  Frappe is live at https://{ctx.site_name}[/bold green]\n",
        f"  [dim]Bench[/dim]    ~/{ctx.bench_name}",
        f"  [dim]Site[/dim]     {ctx.site_name}",
        f"  [dim]App[/dim]      {ctx.app_name}  ({ctx.app_branch})",
        f"  [dim]SSL[/dim]      Let's Encrypt — auto-renews",
    ])
    console.print(Panel(lines, title="[green]Installation Complete[/green]", box=box.ROUNDED))
    console.print("\n  [dim]Next steps:[/dim]")
    console.print("    [cyan]frappe service status[/cyan]   — check running services")
    console.print("    [cyan]frappe site backup[/cyan]      — take a manual backup")
    console.print("    [cyan]frappe ssl setup[/cyan]        — renew SSL certificate\n")


def print_error(console: Console, step_description: str, message: str, hint: str = "") -> None:
    parts = [f"[red]{message}[/red]"]
    if hint.strip():
        parts.append(f"\n  [dim]stderr:[/dim] {hint.strip()[:300]}")
    parts.append("\n  Fix the issue then re-run:")
    parts.append("    [cyan]frappe install --resume[/cyan]")
    console.print(Panel(
        "\n".join(parts),
        title=f"[bold red]Error in: {step_description}[/bold red]",
        box=box.ROUNDED,
    ))
```

- [ ] **Step 6: Create `src/frappe_cli/ui/prompts.py`**

```python
from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..install.context import InstallContext
from ..install.state import InstallState
from .panels import print_header


def _detect_ubuntu_version() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    return line.split("=")[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return "22.04"


def collect_inputs(console: Console, dry_run: bool = False, debug: bool = False) -> InstallContext:
    print_header(console)
    console.print("\n  Let's get your Frappe production server ready.\n")

    console.print("  [bold]── Server Configuration ──[/bold]")
    bench_name = Prompt.ask("  Bench name", default="frappe-bench")
    site_name = Prompt.ask("  Site name (FQDN)")
    frappe_branch = Prompt.ask("  Frappe branch", default="version-15")

    console.print("\n  [bold]── App ──[/bold]")
    app_url = Prompt.ask("  App GitHub URL")
    app_branch = Prompt.ask("  App branch", default=frappe_branch)

    console.print("\n  [bold]── Credentials ──[/bold]")
    sudo_password = Prompt.ask("  Sudo (VPS admin) password", password=True)
    mariadb_root_password = Prompt.ask("  MariaDB root password (will be set)", password=True)
    admin_password = Prompt.ask("  Frappe site admin password", password=True)
    ssl_email = Prompt.ask("  SSL email (Let's Encrypt)")

    ubuntu_version = _detect_ubuntu_version()
    console.print(f"\n  [dim]Detected Ubuntu {ubuntu_version}[/dim]\n")

    if not Confirm.ask("  Ready to install (10–20 min). Continue?", default=True):
        raise SystemExit(0)

    return InstallContext(
        bench_name=bench_name,
        site_name=site_name,
        frappe_branch=frappe_branch,
        app_url=app_url,
        app_branch=app_branch,
        sudo_password=sudo_password,
        mariadb_root_password=mariadb_root_password,
        admin_password=admin_password,
        ssl_email=ssl_email,
        ubuntu_version=ubuntu_version,
        dry_run=dry_run,
        debug=debug,
    )


def collect_credentials_for_resume(console: Console, state: InstallState) -> InstallContext:
    console.print("\n  [yellow]Resuming previous install.[/yellow]")
    console.print(f"  Site: [cyan]{state.site_name}[/cyan]  Bench: [cyan]{state.bench_name}[/cyan]\n")

    console.print("  [bold]── Re-enter credentials ──[/bold]")
    sudo_password = Prompt.ask("  Sudo (VPS admin) password", password=True)
    mariadb_root_password = Prompt.ask("  MariaDB root password", password=True)
    admin_password = Prompt.ask("  Frappe site admin password", password=True)

    return InstallContext(
        bench_name=state.bench_name,
        site_name=state.site_name,
        frappe_branch=state.frappe_branch,
        app_url=state.app_url,
        app_branch=state.app_branch,
        sudo_password=sudo_password,
        mariadb_root_password=mariadb_root_password,
        admin_password=admin_password,
        ssl_email=state.ssl_email,
        ubuntu_version=state.ubuntu_version,
        dry_run=False,
        debug=False,
    )
```

- [ ] **Step 7: Run step renderer tests**

```bash
PYTHONPATH=src poetry run pytest tests/test_ui_steps.py -v
```

Expected: 6 passed

- [ ] **Step 8: Commit**

```bash
git add src/frappe_cli/ui/ tests/test_ui_steps.py
git commit -m "feat: add UI layer (panels, step renderer, prompts)"
```

---

## Task 4: System + uv install steps

**Files:**
- Create: `src/frappe_cli/install/steps/system.py`
- Create: `src/frappe_cli/install/steps/uv_check.py`
- Modify: `tests/test_install_steps.py` (create file)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_install_steps.py
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from frappe_cli.install.context import InstallContext
from frappe_cli.install.steps.base import StepError


def make_ctx(**overrides):
    defaults = dict(
        bench_name="frappe-bench", site_name="mysite.com",
        frappe_branch="version-15", app_url="https://github.com/frappe/erpnext",
        app_branch="version-15", sudo_password="secret",
        mariadb_root_password="dbpass", admin_password="adminpass",
        ssl_email="admin@mysite.com", ubuntu_version="22.04",
        dry_run=False, debug=False,
    )
    defaults.update(overrides)
    return InstallContext(**defaults)


# ── SystemUpdateStep ──────────────────────────────────────────────────────────

class TestSystemUpdateStep:
    def test_check_always_returns_false(self):
        from frappe_cli.install.steps.system import SystemUpdateStep
        step = SystemUpdateStep()
        assert step.check(make_ctx()) is False

    def test_run_calls_apt_update_and_upgrade(self):
        from frappe_cli.install.steps.system import SystemUpdateStep
        step = SystemUpdateStep()
        ctx = make_ctx()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            step.run(ctx)
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("apt-get" in c and "update" in c for c in calls)
        assert any("apt-get" in c and "upgrade" in c for c in calls)

    def test_dry_run_does_not_call_subprocess(self):
        from frappe_cli.install.steps.system import SystemUpdateStep
        step = SystemUpdateStep()
        ctx = make_ctx(dry_run=True)
        with patch("subprocess.run") as mock_run:
            step.run(ctx)
        mock_run.assert_not_called()


# ── SystemDepsStep ────────────────────────────────────────────────────────────

class TestSystemDepsStep:
    def test_check_returns_true_when_all_packages_present(self):
        from frappe_cli.install.steps.system import SystemDepsStep
        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_returns_false_when_package_missing(self):
        from frappe_cli.install.steps.system import SystemDepsStep
        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False

    def test_run_installs_required_packages(self):
        from frappe_cli.install.steps.system import SystemDepsStep, SYSTEM_PACKAGES
        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            step.run(make_ctx())
        all_args = [str(a) for c in mock_run.call_args_list for a in c.args[0]]
        for pkg in SYSTEM_PACKAGES:
            assert pkg in all_args


# ── UvCheckStep ───────────────────────────────────────────────────────────────

class TestUvCheckStep:
    def test_check_returns_true_when_uv_installed(self):
        from frappe_cli.install.steps.uv_check import UvCheckStep
        step = UvCheckStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_returns_false_when_uv_missing(self):
        from frappe_cli.install.steps.uv_check import UvCheckStep
        step = UvCheckStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py -v
```

Expected: `ModuleNotFoundError: No module named 'frappe_cli.install.steps.system'`

- [ ] **Step 3: Create `src/frappe_cli/install/steps/system.py`**

```python
import subprocess
from typing import List

from .base import InstallStep

SYSTEM_PACKAGES: List[str] = [
    "python3-dev", "python3-setuptools", "python3-pip", "python3-venv",
    "git", "build-essential", "libssl-dev", "libffi-dev", "curl",
    "software-properties-common", "xvfb", "libfontconfig",
]


class SystemUpdateStep(InstallStep):
    name = "system_update"
    description = "System update & upgrade"

    def check(self, ctx) -> bool:
        return False

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "update", "-y"])
        self._sudo(ctx, ["apt-get", "upgrade", "-y", "-o", "Dpkg::Options::=--force-confdef"])


class SystemDepsStep(InstallStep):
    name = "system_deps"
    description = "Install system dependencies"

    def check(self, ctx) -> bool:
        for pkg in SYSTEM_PACKAGES:
            result = subprocess.run(
                ["dpkg", "-l", pkg], capture_output=True, text=True
            )
            if result.returncode != 0:
                return False
        return True

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "install", "-y"] + SYSTEM_PACKAGES)
```

- [ ] **Step 4: Create `src/frappe_cli/install/steps/uv_check.py`**

```python
import os
import subprocess
from pathlib import Path

from .base import InstallStep, StepError


class UvCheckStep(InstallStep):
    name = "uv_check"
    description = "Verify uv"

    def check(self, ctx) -> bool:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def run(self, ctx) -> None:
        if ctx.dry_run:
            return
        try:
            script = subprocess.run(
                ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
                capture_output=True, check=True,
            )
            subprocess.run(["sh"], input=script.stdout, check=True)
        except subprocess.CalledProcessError as e:
            raise StepError("Failed to install uv", hint=str(e))

        local_bin = str(Path.home() / ".local" / "bin")
        current = os.environ.get("PATH", "")
        if local_bin not in current:
            os.environ["PATH"] = f"{local_bin}:{current}"
```

- [ ] **Step 5: Run tests**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py::TestSystemUpdateStep \
  tests/test_install_steps.py::TestSystemDepsStep \
  tests/test_install_steps.py::TestUvCheckStep -v
```

Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/frappe_cli/install/steps/system.py src/frappe_cli/install/steps/uv_check.py \
        tests/test_install_steps.py
git commit -m "feat: add SystemUpdate, SystemDeps, UvCheck install steps"
```

---

## Task 5: Node.js, MariaDB, Redis steps

**Files:**
- Create: `src/frappe_cli/install/steps/nodejs.py`
- Create: `src/frappe_cli/install/steps/mariadb.py`
- Create: `src/frappe_cli/install/steps/redis.py`

- [ ] **Step 1: Add tests to `tests/test_install_steps.py`** (append)

```python
# ── NodeJSStep ────────────────────────────────────────────────────────────────

class TestNodeJSStep:
    def test_check_true_when_node_present(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert NodeJSStep().check(make_ctx()) is True

    def test_check_false_when_node_missing(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert NodeJSStep().check(make_ctx()) is False

    def test_run_uses_node18_for_2204(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        ctx = make_ctx(ubuntu_version="22.04")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            NodeJSStep().run(ctx)
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "18" in all_args

    def test_run_uses_node20_for_2404(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep
        ctx = make_ctx(ubuntu_version="24.04")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            NodeJSStep().run(ctx)
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "20" in all_args


# ── MariaDB ───────────────────────────────────────────────────────────────────

class TestMariaDBInstallStep:
    def test_check_true_when_running_and_config_exists(self, tmp_path):
        from frappe_cli.install.steps.mariadb import MariaDBInstallStep
        step = MariaDBInstallStep()
        fake_cnf = tmp_path / "99-frappe.cnf"
        fake_cnf.write_text("[mysqld]")
        with patch("subprocess.run") as mock_run, \
             patch.object(step, "CNF_PATH", str(fake_cnf)):
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_false_when_mysqladmin_fails(self):
        from frappe_cli.install.steps.mariadb import MariaDBInstallStep
        step = MariaDBInstallStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False


class TestMariaDBSecureStep:
    def test_check_true_when_password_auth_works(self):
        from frappe_cli.install.steps.mariadb import MariaDBSecureStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert MariaDBSecureStep().check(make_ctx()) is True

    def test_check_false_when_auth_fails(self):
        from frappe_cli.install.steps.mariadb import MariaDBSecureStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert MariaDBSecureStep().check(make_ctx()) is False


# ── RedisStep ─────────────────────────────────────────────────────────────────

class TestRedisStep:
    def test_check_true_when_ping_returns_pong(self):
        from frappe_cli.install.steps.redis import RedisStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="PONG\n")
            assert RedisStep().check(make_ctx()) is True

    def test_check_false_when_ping_fails(self):
        from frappe_cli.install.steps.redis import RedisStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert RedisStep().check(make_ctx()) is False
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py::TestNodeJSStep \
  tests/test_install_steps.py::TestMariaDBInstallStep \
  tests/test_install_steps.py::TestRedisStep -v
```

Expected: import errors

- [ ] **Step 3: Create `src/frappe_cli/install/steps/nodejs.py`**

```python
import subprocess
from .base import InstallStep, StepError


class NodeJSStep(InstallStep):
    name = "nodejs"
    description = "Install Node.js + Yarn"

    def check(self, ctx) -> bool:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def run(self, ctx) -> None:
        node_version = "18" if ctx.ubuntu_version == "22.04" else "20"
        try:
            script = subprocess.run(
                ["curl", "-fsSL", f"https://deb.nodesource.com/setup_{node_version}.x"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["sudo", "-S", "bash"],
                input=(ctx.sudo_password + "\n").encode() + script.stdout,
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise StepError("Failed to run NodeSource setup script", hint=e.stderr.decode(errors="replace"))
        self._sudo(ctx, ["apt-get", "install", "-y", "nodejs"])
        self._sudo(ctx, ["npm", "install", "-g", "yarn"])
```

- [ ] **Step 4: Create `src/frappe_cli/install/steps/mariadb.py`**

```python
import subprocess
from pathlib import Path
from .base import InstallStep, StepError

FRAPPE_MARIADB_CNF = """\
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""


class MariaDBInstallStep(InstallStep):
    name = "mariadb_install"
    description = "Install & configure MariaDB"
    CNF_PATH = "/etc/mysql/mariadb.conf.d/99-frappe.cnf"

    def check(self, ctx) -> bool:
        result = subprocess.run(["mysqladmin", "status"], capture_output=True, text=True)
        return result.returncode == 0 and Path(self.CNF_PATH).exists()

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "install", "-y", "mariadb-server", "mariadb-client"])
        self._sudo_write(ctx, FRAPPE_MARIADB_CNF, self.CNF_PATH)
        self._sudo(ctx, ["systemctl", "enable", "mariadb"])
        self._sudo(ctx, ["systemctl", "restart", "mariadb"])


class MariaDBSecureStep(InstallStep):
    name = "mariadb_secure"
    description = "Secure MariaDB"

    def check(self, ctx) -> bool:
        result = subprocess.run(
            ["mysql", "-u", "root", f"-p{ctx.mariadb_root_password}", "-e", "SELECT 1;"],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    def run(self, ctx) -> None:
        pw = ctx.mariadb_root_password.replace("'", "\\'")
        sql = (
            f"ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password "
            f"USING PASSWORD('{pw}'); "
            "DELETE FROM mysql.user WHERE User=''; "
            "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN "
            "('localhost', '127.0.0.1', '::1'); "
            "DROP DATABASE IF EXISTS test; "
            "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%'; "
            "FLUSH PRIVILEGES;"
        )
        self._sudo(ctx, ["mysql", "-e", sql])
```

- [ ] **Step 5: Create `src/frappe_cli/install/steps/redis.py`**

```python
import subprocess
from .base import InstallStep


class RedisStep(InstallStep):
    name = "redis"
    description = "Install Redis"

    def check(self, ctx) -> bool:
        result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
        return result.returncode == 0 and "PONG" in result.stdout

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "install", "-y", "redis-server"])
        self._sudo(ctx, ["systemctl", "enable", "redis-server"])
        self._sudo(ctx, ["systemctl", "start", "redis-server"])
```

- [ ] **Step 6: Run tests**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py -v
```

Expected: all step tests pass

- [ ] **Step 7: Commit**

```bash
git add src/frappe_cli/install/steps/nodejs.py \
        src/frappe_cli/install/steps/mariadb.py \
        src/frappe_cli/install/steps/redis.py
git commit -m "feat: add Node.js, MariaDB, Redis install steps"
```

---

## Task 6: wkhtmltopdf, bench, init, site steps

**Files:**
- Create: `src/frappe_cli/install/steps/wkhtmltopdf.py`
- Create: `src/frappe_cli/install/steps/bench.py`
- Create: `src/frappe_cli/install/steps/init_bench.py`
- Create: `src/frappe_cli/install/steps/site.py`

- [ ] **Step 1: Append tests to `tests/test_install_steps.py`**

```python
# ── WkhtmltopdfStep ───────────────────────────────────────────────────────────

class TestWkhtmltopdfStep:
    def test_check_true_when_installed(self):
        from frappe_cli.install.steps.wkhtmltopdf import WkhtmltopdfStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="wkhtmltopdf 0.12.6")
            assert WkhtmltopdfStep().check(make_ctx()) is True

    def test_check_false_when_not_installed(self):
        from frappe_cli.install.steps.wkhtmltopdf import WkhtmltopdfStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert WkhtmltopdfStep().check(make_ctx()) is False


# ── BenchInstallStep ──────────────────────────────────────────────────────────

class TestBenchInstallStep:
    def test_check_true_when_bench_present(self):
        from frappe_cli.install.steps.bench import BenchInstallStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert BenchInstallStep().check(make_ctx()) is True

    def test_run_calls_uv_tool_install(self):
        from frappe_cli.install.steps.bench import BenchInstallStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            BenchInstallStep().run(make_ctx())
        all_args = [c.args[0] for c in mock_run.call_args_list]
        assert any("uv" in a and "tool" in a and "install" in a for a in all_args)


# ── BenchInitStep ─────────────────────────────────────────────────────────────

class TestBenchInitStep:
    def test_check_true_when_apps_frappe_exists(self, tmp_path):
        from frappe_cli.install.steps.init_bench import BenchInitStep
        (tmp_path / "apps" / "frappe").mkdir(parents=True)
        ctx = make_ctx(bench_name=tmp_path.name)
        with patch.object(ctx, "bench_path", new=tmp_path):
            assert BenchInitStep().check(ctx) is True

    def test_check_false_when_bench_missing(self, tmp_path):
        from frappe_cli.install.steps.init_bench import BenchInitStep
        ctx = make_ctx(bench_name="nonexistent-bench")
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert BenchInitStep().check(ctx) is False

    def test_run_calls_bench_init(self):
        from frappe_cli.install.steps.init_bench import BenchInitStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            BenchInitStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "bench" in all_args and "init" in all_args


# ── SiteCreateStep ────────────────────────────────────────────────────────────

class TestSiteCreateStep:
    def test_check_true_when_site_config_exists(self, tmp_path):
        from frappe_cli.install.steps.site import SiteCreateStep
        site_dir = tmp_path / "sites" / "mysite.com"
        site_dir.mkdir(parents=True)
        (site_dir / "site_config.json").write_text("{}")
        ctx = make_ctx(site_name="mysite.com")
        with patch.object(ctx, "bench_path", new=tmp_path):
            assert SiteCreateStep().check(ctx) is True

    def test_check_false_when_site_missing(self, tmp_path):
        from frappe_cli.install.steps.site import SiteCreateStep
        ctx = make_ctx(site_name="mysite.com")
        with patch.object(ctx, "bench_path", new=tmp_path):
            assert SiteCreateStep().check(ctx) is False

    def test_run_calls_bench_new_site_with_passwords(self):
        from frappe_cli.install.steps.site import SiteCreateStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            SiteCreateStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "new-site" in all_args
        assert "dbpass" in all_args
        assert "adminpass" in all_args
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py::TestWkhtmltopdfStep \
  tests/test_install_steps.py::TestBenchInstallStep \
  tests/test_install_steps.py::TestBenchInitStep \
  tests/test_install_steps.py::TestSiteCreateStep -v
```

Expected: import errors

- [ ] **Step 3: Create `src/frappe_cli/install/steps/wkhtmltopdf.py`**

```python
import subprocess
from .base import InstallStep


class WkhtmltopdfStep(InstallStep):
    name = "wkhtmltopdf"
    description = "Install wkhtmltopdf"

    def check(self, ctx) -> bool:
        result = subprocess.run(["wkhtmltopdf", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def run(self, ctx) -> None:
        packages = ["wkhtmltopdf", "libxrender1", "xfonts-75dpi", "xfonts-base", "fontconfig"]
        self._sudo(ctx, ["apt-get", "install", "-y"] + packages)
```

- [ ] **Step 4: Create `src/frappe_cli/install/steps/bench.py`**

```python
import subprocess
from .base import InstallStep


class BenchInstallStep(InstallStep):
    name = "bench_install"
    description = "Install frappe-bench (uv)"

    def check(self, ctx) -> bool:
        result = subprocess.run(["bench", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def run(self, ctx) -> None:
        self._run(ctx, ["uv", "tool", "install", "frappe-bench"])
```

- [ ] **Step 5: Create `src/frappe_cli/install/steps/init_bench.py`**

```python
import subprocess
from pathlib import Path
from .base import InstallStep


class BenchInitStep(InstallStep):
    name = "bench_init"
    description = "Initialize bench"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "apps" / "frappe").exists()

    def run(self, ctx) -> None:
        self._run(ctx, [
            "bench", "init", ctx.bench_name,
            "--frappe-branch", ctx.frappe_branch,
        ], cwd=str(Path.home()))
```

- [ ] **Step 6: Create `src/frappe_cli/install/steps/site.py`**

```python
from pathlib import Path
from .base import InstallStep


class SiteCreateStep(InstallStep):
    name = "site_create"
    description = "Create site"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "sites" / ctx.site_name / "site_config.json").exists()

    def run(self, ctx) -> None:
        self._run(ctx, [
            "bench", "new-site", ctx.site_name,
            "--mariadb-root-username", "root",
            "--mariadb-root-password", ctx.mariadb_root_password,
            "--admin-password", ctx.admin_password,
        ], cwd=str(ctx.bench_path))
```

- [ ] **Step 7: Run all step tests**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py -v
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add src/frappe_cli/install/steps/wkhtmltopdf.py \
        src/frappe_cli/install/steps/bench.py \
        src/frappe_cli/install/steps/init_bench.py \
        src/frappe_cli/install/steps/site.py
git commit -m "feat: add wkhtmltopdf, bench-install, bench-init, site-create steps"
```

---

## Task 7: App, production, SSL steps + steps registry

**Files:**
- Create: `src/frappe_cli/install/steps/app.py`
- Create: `src/frappe_cli/install/steps/production.py`
- Create: `src/frappe_cli/install/steps/ssl.py`
- Modify: `src/frappe_cli/install/steps/__init__.py`

- [ ] **Step 1: Append tests to `tests/test_install_steps.py`**

```python
# ── AppGetStep ────────────────────────────────────────────────────────────────

class TestAppGetStep:
    def test_check_true_when_app_dir_exists(self, tmp_path):
        from frappe_cli.install.steps.app import AppGetStep
        (tmp_path / "apps" / "erpnext").mkdir(parents=True)
        ctx = make_ctx()
        with patch.object(ctx, "bench_path", new=tmp_path):
            assert AppGetStep().check(ctx) is True

    def test_check_false_when_app_missing(self, tmp_path):
        from frappe_cli.install.steps.app import AppGetStep
        ctx = make_ctx()
        with patch.object(ctx, "bench_path", new=tmp_path):
            assert AppGetStep().check(ctx) is False

    def test_run_calls_bench_get_app(self):
        from frappe_cli.install.steps.app import AppGetStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            AppGetStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "get-app" in all_args


# ── AppInstallStep ────────────────────────────────────────────────────────────

class TestAppInstallStep:
    def test_check_true_when_app_listed(self):
        from frappe_cli.install.steps.app import AppInstallStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="erpnext\nfrappe\n")
            assert AppInstallStep().check(make_ctx()) is True

    def test_check_false_when_app_not_listed(self):
        from frappe_cli.install.steps.app import AppInstallStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="frappe\n")
            assert AppInstallStep().check(make_ctx()) is False


# ── SSLSetupStep ──────────────────────────────────────────────────────────────

class TestSSLSetupStep:
    def test_check_true_when_cert_exists(self, tmp_path):
        from frappe_cli.install.steps.ssl import SSLSetupStep
        cert_dir = tmp_path / "live" / "mysite.com"
        cert_dir.mkdir(parents=True)
        (cert_dir / "fullchain.pem").write_text("cert")
        step = SSLSetupStep()
        with patch.object(step, "_cert_path", return_value=cert_dir / "fullchain.pem"):
            assert step.check(make_ctx()) is True

    def test_run_calls_certbot(self):
        from frappe_cli.install.steps.ssl import SSLSetupStep
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            SSLSetupStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "certbot" in all_args
        assert "mysite.com" in all_args
        assert "admin@mysite.com" in all_args


# ── ALL_STEPS registry ────────────────────────────────────────────────────────

def test_all_steps_has_correct_count():
    from frappe_cli.install.steps import ALL_STEPS
    assert len(ALL_STEPS) == 15


def test_all_steps_have_unique_names():
    from frappe_cli.install.steps import ALL_STEPS
    names = [s.name for s in ALL_STEPS]
    assert len(names) == len(set(names))
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py::TestAppGetStep \
  tests/test_install_steps.py::TestSSLSetupStep \
  tests/test_install_steps.py::test_all_steps_has_correct_count -v
```

Expected: import errors

- [ ] **Step 3: Create `src/frappe_cli/install/steps/app.py`**

```python
import subprocess
from .base import InstallStep


class AppGetStep(InstallStep):
    name = "app_get"
    description = "Get app from GitHub"

    def check(self, ctx) -> bool:
        return (ctx.bench_path / "apps" / ctx.app_name).exists()

    def run(self, ctx) -> None:
        self._run(ctx, [
            "bench", "get-app", ctx.app_url,
            "--branch", ctx.app_branch,
        ], cwd=str(ctx.bench_path))


class AppInstallStep(InstallStep):
    name = "app_install"
    description = "Install app on site"

    def check(self, ctx) -> bool:
        result = subprocess.run(
            ["bench", "--site", ctx.site_name, "list-apps"],
            capture_output=True, text=True,
            cwd=str(ctx.bench_path),
        )
        return ctx.app_name in result.stdout

    def run(self, ctx) -> None:
        self._run(ctx, [
            "bench", "--site", ctx.site_name,
            "install-app", ctx.app_name,
        ], cwd=str(ctx.bench_path))
```

- [ ] **Step 4: Create `src/frappe_cli/install/steps/production.py`**

```python
import getpass
import os
import subprocess
import tempfile
from .base import InstallStep, StepError
from pathlib import Path


class ProductionSetupStep(InstallStep):
    name = "production_setup"
    description = "Setup production (nginx + supervisor)"

    def check(self, ctx) -> bool:
        bench_conf = Path(f"/etc/nginx/conf.d/{ctx.bench_name}.conf")
        return bench_conf.exists()

    def run(self, ctx) -> None:
        if ctx.dry_run:
            return
        current_user = getpass.getuser()
        askpass = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
        try:
            askpass.write(f"#!/bin/sh\necho '{ctx.sudo_password}'\n")
            askpass.close()
            os.chmod(askpass.name, 0o700)
            env = os.environ.copy()
            env["SUDO_ASKPASS"] = askpass.name
            result = subprocess.run(
                ["bench", "setup", "production", current_user, "--yes"],
                cwd=str(ctx.bench_path),
                capture_output=True, text=True,
                env=env,
            )
            if result.returncode != 0:
                raise StepError("bench setup production failed", hint=result.stderr)
        finally:
            os.unlink(askpass.name)
```

- [ ] **Step 5: Create `src/frappe_cli/install/steps/ssl.py`**

```python
import subprocess
from pathlib import Path
from .base import InstallStep


class SSLSetupStep(InstallStep):
    name = "ssl_setup"
    description = "Configure SSL (Let's Encrypt)"

    def _cert_path(self, ctx) -> Path:
        return Path(f"/etc/letsencrypt/live/{ctx.site_name}/fullchain.pem")

    def check(self, ctx) -> bool:
        return self._cert_path(ctx).exists()

    def run(self, ctx) -> None:
        result = subprocess.run(["which", "certbot"], capture_output=True)
        if result.returncode != 0:
            self._sudo(ctx, ["apt-get", "install", "-y", "certbot", "python3-certbot-nginx"])
        self._sudo(ctx, [
            "certbot", "--nginx",
            "-d", ctx.site_name,
            "--non-interactive", "--agree-tos",
            "-m", ctx.ssl_email,
        ])
        self._sudo(ctx, ["systemctl", "enable", "certbot.timer"])
        self._sudo(ctx, ["systemctl", "start", "certbot.timer"])
```

- [ ] **Step 6: Populate `src/frappe_cli/install/steps/__init__.py`**

```python
from .system import SystemUpdateStep, SystemDepsStep
from .uv_check import UvCheckStep
from .nodejs import NodeJSStep
from .mariadb import MariaDBInstallStep, MariaDBSecureStep
from .redis import RedisStep
from .wkhtmltopdf import WkhtmltopdfStep
from .bench import BenchInstallStep
from .init_bench import BenchInitStep
from .site import SiteCreateStep
from .app import AppGetStep, AppInstallStep
from .production import ProductionSetupStep
from .ssl import SSLSetupStep

ALL_STEPS = [
    SystemUpdateStep(),
    SystemDepsStep(),
    UvCheckStep(),
    NodeJSStep(),
    MariaDBInstallStep(),
    MariaDBSecureStep(),
    RedisStep(),
    WkhtmltopdfStep(),
    BenchInstallStep(),
    BenchInitStep(),
    SiteCreateStep(),
    AppGetStep(),
    AppInstallStep(),
    ProductionSetupStep(),
    SSLSetupStep(),
]
```

- [ ] **Step 7: Run all step tests**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_steps.py -v
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add src/frappe_cli/install/steps/
git commit -m "feat: add app, production, SSL steps and steps registry"
```

---

## Task 8: Wizard orchestrator

**Files:**
- Create: `src/frappe_cli/install/wizard.py`
- Modify: `src/frappe_cli/install/__init__.py`
- Create: `tests/test_install_wizard.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_install_wizard.py
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from frappe_cli.cli import cli


def _mock_inputs():
    """Simulate user typing answers to all prompts."""
    return (
        "frappe-bench\n"   # bench name
        "mysite.com\n"     # site name
        "version-15\n"     # frappe branch
        "https://github.com/frappe/erpnext\n"  # app url
        "version-15\n"     # app branch
        "sudopass\n"       # sudo password
        "dbpass\n"         # mariadb root
        "adminpass\n"      # admin password
        "admin@mysite.com\n"  # ssl email
        "y\n"              # confirm
    )


def test_install_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["install", "wizard", "--help"])
    assert result.exit_code == 0
    assert "--resume" in result.output


def test_install_dry_run_completes_all_steps():
    runner = CliRunner()
    from frappe_cli.install.context import InstallContext
    ctx = InstallContext(
        bench_name="frappe-bench", site_name="mysite.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15", sudo_password="s",
        mariadb_root_password="d", admin_password="a",
        ssl_email="e@e.com", ubuntu_version="22.04",
        dry_run=True,
    )
    step = MagicMock()
    step.name = "test_step"
    step.description = "Test step"
    step.check.return_value = False
    # Patch ALL_STEPS as a real list so it can be iterated twice
    # (once for renderer, once for the main loop)
    with patch("frappe_cli.install.wizard.collect_inputs", return_value=ctx), \
         patch("frappe_cli.install.wizard.ALL_STEPS", [step]), \
         patch("frappe_cli.install.wizard.save_state"), \
         patch("frappe_cli.install.wizard.clear_state"):
        result = runner.invoke(cli, ["install", "wizard", "--dry-run"])
    assert result.exit_code == 0


def test_install_resume_fails_without_state():
    runner = CliRunner()
    with patch("frappe_cli.install.wizard.state_exists", return_value=False):
        result = runner.invoke(cli, ["install", "wizard", "--resume"])
    assert result.exit_code != 0


def test_install_step_failure_exits_nonzero():
    runner = CliRunner()
    from frappe_cli.install.steps.base import StepError
    from frappe_cli.install.context import InstallContext
    ctx = InstallContext(
        bench_name="b", site_name="s.com", frappe_branch="v15",
        app_url="https://github.com/frappe/erpnext", app_branch="v15",
        sudo_password="s", mariadb_root_password="d",
        admin_password="a", ssl_email="e@e.com",
        ubuntu_version="22.04", dry_run=False,
    )
    step = MagicMock()
    step.name = "failing_step"
    step.description = "Failing step"
    step.check.return_value = False
    step.run.side_effect = StepError("Something broke", hint="stderr output")
    with patch("frappe_cli.install.wizard.collect_inputs", return_value=ctx), \
         patch("frappe_cli.install.wizard.ALL_STEPS", [step]), \
         patch("frappe_cli.install.wizard.save_state"):
        result = runner.invoke(cli, ["install", "wizard"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_wizard.py::test_install_help -v
```

Expected: `Error: No such command 'wizard'`

- [ ] **Step 3: Create `src/frappe_cli/install/wizard.py`**

```python
import sys
import time

import click
from rich.console import Console
from rich.live import Live

from ..ui.panels import print_error, print_success
from ..ui.prompts import collect_credentials_for_resume, collect_inputs
from ..ui.steps import StepListRenderer
from .context import InstallContext
from .state import InstallState, clear_state, load_state, save_state, state_exists
from .steps import ALL_STEPS
from .steps.base import StepError

console = Console()


@click.command()
@click.option("--resume", is_flag=True, help="Resume from the last failed step")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
@click.option("--debug", is_flag=True, help="Show full command output during execution")
def wizard(resume, dry_run, debug):
    """Interactive production installer for Frappe."""
    if resume:
        if not state_exists():
            console.print("[red]No previous install state found. Run 'frappe install wizard'.[/red]")
            sys.exit(1)
        state = load_state()
        ctx = collect_credentials_for_resume(console, state)
        completed_steps = set(state.completed_steps)
    else:
        ctx = collect_inputs(console, dry_run=dry_run, debug=debug)
        completed_steps = set()

    renderer = StepListRenderer([s.description for s in ALL_STEPS])
    for step in ALL_STEPS:
        if step.name in completed_steps:
            renderer.mark_skipped(step.description)

    failed = None

    with Live(renderer.render(), console=console, refresh_per_second=4) as live:
        for step in ALL_STEPS:
            if step.name in completed_steps:
                continue

            start = time.monotonic()
            renderer.mark_running(step.description)
            live.update(renderer.render())

            try:
                if step.check(ctx):
                    renderer.mark_skipped(step.description)
                else:
                    step.run(ctx)
                    renderer.mark_done(step.description)

                completed_steps.add(step.name)
                save_state(InstallState(
                    bench_name=ctx.bench_name,
                    site_name=ctx.site_name,
                    frappe_branch=ctx.frappe_branch,
                    app_url=ctx.app_url,
                    app_branch=ctx.app_branch,
                    ssl_email=ctx.ssl_email,
                    ubuntu_version=ctx.ubuntu_version,
                    completed_steps=list(completed_steps),
                ))

            except StepError as e:
                renderer.mark_failed(step.description)
                live.update(renderer.render())
                failed = (step, e)
                break

            renderer.update_elapsed(step.description, time.monotonic() - start)
            live.update(renderer.render())

    if failed:
        step, err = failed
        print_error(console, step.description, err.message, err.hint)
        sys.exit(1)

    clear_state()
    print_success(console, ctx)
```

- [ ] **Step 4: Register wizard in `src/frappe_cli/install/__init__.py`**

```python
import click

from .bench import bench
from .deps import deps
from .fail2ban import fail2ban
from .init import init
from .mariadb import mariadb
from .prod import prod
from .ssh_hardening import ssh_hardening
from .system import system
from .user import user
from .wizard import wizard


@click.group()
def install():
    """Install and setup commands for Frappe"""
    pass


install.add_command(bench)
install.add_command(deps)
install.add_command(fail2ban)
install.add_command(init)
install.add_command(mariadb)
install.add_command(prod)
install.add_command(ssh_hardening)
install.add_command(system)
install.add_command(user)
install.add_command(wizard)
```

- [ ] **Step 5: Run wizard tests**

```bash
PYTHONPATH=src poetry run pytest tests/test_install_wizard.py -v
```

Expected: all pass

- [ ] **Step 6: Verify the command appears in help**

```bash
PYTHONPATH=src poetry run frappe install --help
```

Expected: `wizard` listed as a command

- [ ] **Step 7: Commit**

```bash
git add src/frappe_cli/install/wizard.py src/frappe_cli/install/__init__.py \
        tests/test_install_wizard.py
git commit -m "feat: add frappe install wizard orchestrator"
```

---

## Task 9: Deduplication — remove copied RichShell/logger from existing modules

**Files to modify:**
- `src/frappe_cli/install/system.py`
- `src/frappe_cli/install/mariadb.py`
- `src/frappe_cli/install/prod.py`
- `src/frappe_cli/install/bench.py`
- `src/frappe_cli/install/deps.py`
- `src/frappe_cli/install/user.py`
- `src/frappe_cli/install/init.py`
- `src/frappe_cli/install/fail2ban.py`
- `src/frappe_cli/install/ssh_hardening.py`
- `src/frappe_cli/ssl/setup.py`
- `src/frappe_cli/service/restart.py`
- `src/frappe_cli/service/status.py`

- [ ] **Step 1: Run the existing test suite to get a baseline**

```bash
PYTHONPATH=src poetry run pytest tests/ -v --tb=short 2>&1 | tail -20
```

Note the number of passing tests — this should not decrease after this task.

- [ ] **Step 2: For each module listed above — remove the local `RichShell` class and `setup_logger` function, replace with imports**

The pattern to apply in every affected file:

**Remove** any block that looks like:
```python
class RichShell:
    def __init__(self, console, dry_run=False, debug=False): ...
    def run(self, cmd, ...): ...

def setup_logger():
    logger = logging.getLogger(...)
    ...
    return logger

logger = setup_logger()
```

**Replace the logger setup** with:
```python
from ..utils.logging import get_logger
logger = get_logger("install.system")   # adjust module name per file
```

**Replace the RichShell instantiation** (search for `RichShell(console` in each file):
```python
# Before
shell = RichShell(console, dry_run=dry_run, debug=debug)

# After
from ..utils.shell import RichShellRunner
shell = RichShellRunner(console=console, dry_run=dry_run, debug=debug, module_name="install.system")
```

Work through each file one at a time. After modifying each file, run:
```bash
PYTHONPATH=src poetry run python -c "import frappe_cli.install.<module_name>"
```
to verify the import still works.

- [ ] **Step 3: Run full test suite**

```bash
PYTHONPATH=src poetry run pytest tests/ -v
```

Expected: same number of tests pass as baseline (no regressions)

- [ ] **Step 4: Run linter**

```bash
poetry run ruff check src/ tests/
poetry run black --check src/ tests/
```

Fix any issues found.

- [ ] **Step 5: Commit**

```bash
git add src/
git commit -m "refactor: remove duplicated RichShell and setup_logger from all modules"
```

---

## Final verification

- [ ] **Run the complete test suite**

```bash
PYTHONPATH=src poetry run pytest tests/ -v --tb=short
```

Expected: all tests pass

- [ ] **Run full lint check**

```bash
bash scripts/lint.sh
```

Expected: `All checks passed!`

- [ ] **Smoke-test the CLI**

```bash
PYTHONPATH=src poetry run frappe --help
PYTHONPATH=src poetry run frappe install --help
PYTHONPATH=src poetry run frappe install wizard --help
PYTHONPATH=src poetry run frappe install wizard --dry-run
```

Expected: wizard command visible, `--dry-run` flag listed, dry-run exits cleanly

- [ ] **Final commit**

```bash
git add -A
git commit -m "feat: frappe install wizard — complete production installer with resume support"
```
