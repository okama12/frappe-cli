from dataclasses import dataclass
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
