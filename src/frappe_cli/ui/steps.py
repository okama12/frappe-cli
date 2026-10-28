import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, Group
from rich.panel import Panel
from rich.progress_bar import ProgressBar
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
        self._logs.append(line)

    def set_current(self, name: str) -> None:
        self._current = name
        self._logs.clear()

    def render(self, width: int = 80, height: int = 40) -> Group:
        self._frame += 1
        spin = SPINNER[self._frame % len(SPINNER)]

        table = Table.grid(padding=(0, 1))
        table.add_column(width=1)
        table.add_column(overflow="fold")
        table.add_column(width=7, justify="right")

        # Keep the running row visible on short SSH terminals.
        limit = max(3, (height - 15) // (2 if width < 60 else 1))
        current = next(
            (
                i
                for i, s in enumerate(self._steps)
                if s.status in {StepStatus.RUNNING, StepStatus.FAILED}
            ),
            len(self._steps) - 1,
        )
        start = max(0, min(current - 2, len(self._steps) - limit))
        visible = self._steps[start : start + limit]
        if start:
            table.add_row(
                Text("…", style="dim"),
                Text(f"{start} earlier steps", style="dim"),
                Text(""),
            )
        for step in visible:
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

        remaining = len(self._steps) - start - len(visible)
        if remaining:
            table.add_row(
                Text("…", style="dim"),
                Text(f"{remaining} more steps", style="dim"),
                Text(""),
            )
        completed = sum(
            s.status in {StepStatus.DONE, StepStatus.SKIPPED} for s in self._steps
        )
        content_width = min(
            max(1, width - 4),
            max(
                24,
                max(
                    (
                        cell_len(s.name) + (16 if s.status == StepStatus.SKIPPED else 0)
                        for s in self._steps
                    ),
                    default=0,
                )
                + 12,
            ),
        )
        steps_panel = Panel(
            Group(
                Text(f"{completed}/{len(self._steps)} complete", style="dim"),
                ProgressBar(
                    total=max(1, len(self._steps)),
                    completed=completed,
                    width=content_width,
                ),
                table,
            ),
            title="[bold] Setup progress [/bold]",
            border_style="cyan",
            padding=(0, 1),
            expand=False,
        )

        log_lines = Text(no_wrap=True, overflow="ellipsis")
        if self._logs:
            log_lines.append(
                "\n".join(list(self._logs)[-max(2, min(5, height // 6)) :]), style="dim"
            )
        else:
            log_lines.append("Waiting for output...", style="dim italic")

        title = Text(self._current or "Recent output", style="cyan")
        log_panel = Panel(
            log_lines, title=title, border_style="dim", padding=(0, 1), expand=False
        )

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
        yield self.render(width=options.max_width, height=console.size.height)
