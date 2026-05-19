import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console, ConsoleOptions, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
LOG_LINES = 10


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
    _start: float = field(default=0.0, repr=False)
    elapsed: float = 0.0

    def start(self) -> None:
        self._start = time.monotonic()

    def finish(self) -> None:
        if self._start:
            self.elapsed = time.monotonic() - self._start

    def live_elapsed(self) -> float:
        if self.status == StepStatus.RUNNING and self._start:
            return time.monotonic() - self._start
        return self.elapsed


def _fmt_time(seconds: float) -> str:
    if seconds < 1:
        return ""
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


class StepListRenderer:
    def __init__(self, step_names: list[str]):
        self._steps = [StepDisplay(name=s) for s in step_names]
        self._logs: deque = deque(maxlen=LOG_LINES)
        self._current: str = ""
        self._frame: int = 0

    def add_log(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        low = line.lower()
        if "[sudo]" in low or low.startswith("password"):
            return
        if len(line) > 90:
            line = line[:87] + "..."
        self._logs.append(line)

    def set_current(self, name: str) -> None:
        self._current = name
        self._logs.clear()

    def render(self) -> Group:
        self._frame += 1
        spin = SPINNER[self._frame % len(SPINNER)]

        table = Table.grid(padding=(0, 2))
        table.add_column(width=3)
        table.add_column(min_width=42)
        table.add_column(width=8, justify="right")

        for step in self._steps:
            t = _fmt_time(step.live_elapsed())
            if step.status == StepStatus.DONE:
                table.add_row(
                    Text("✓", style="bold green"),
                    Text(step.name, style="green"),
                    Text(t, style="dim green"),
                )
            elif step.status == StepStatus.SKIPPED:
                table.add_row(
                    Text("✓", style="dim green"),
                    Text(f"{step.name}  [already done]", style="dim green"),
                    Text(""),
                )
            elif step.status == StepStatus.RUNNING:
                table.add_row(
                    Text(spin, style="bold cyan"),
                    Text(step.name, style="bold cyan"),
                    Text(t, style="dim cyan"),
                )
            elif step.status == StepStatus.FAILED:
                table.add_row(
                    Text("✗", style="bold red"),
                    Text(step.name, style="bold red"),
                    Text(t, style="dim red"),
                )
            else:
                table.add_row(
                    Text("○", style="dim"),
                    Text(step.name, style="dim"),
                    Text(""),
                )

        steps_panel = Panel(
            table,
            title="[bold] Installing Frappe Production Stack [/bold]",
            border_style="blue",
            padding=(0, 1),
            expand=False,
        )

        log_lines = Text()
        if self._logs:
            for line in self._logs:
                log_lines.append(line + "\n", style="dim")
        else:
            log_lines.append("Waiting for output...", style="dim italic")

        title = (
            f"[bold cyan]▶  {self._current}[/bold cyan]" if self._current else "Output"
        )
        log_panel = Panel(log_lines, title=title, border_style="dim", padding=(0, 1), expand=False)

        return Group(steps_panel, log_panel)

    def _find(self, name: str) -> StepDisplay | None:
        return next((s for s in self._steps if s.name == name), None)

    def mark_running(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.RUNNING
            s.start()

    def mark_done(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.DONE
            s.finish()

    def mark_skipped(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.SKIPPED

    def mark_failed(self, name: str) -> None:
        s = self._find(name)
        if s:
            s.status = StepStatus.FAILED
            s.finish()

    def update_elapsed(self, name: str, elapsed: float) -> None:
        pass  # handled automatically via start/finish

    def __rich_console__(self, console: Console, options: ConsoleOptions):
        yield self.render()
