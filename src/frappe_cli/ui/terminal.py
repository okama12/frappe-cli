"""Keyboard-driven prompts, with a plain fallback for redirected input."""

import shutil
import sys
from typing import Any

import click
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.utils import get_style
from prompt_toolkit.layout import HSplit, Layout, VSplit
from prompt_toolkit.layout.containers import HorizontalAlign
from prompt_toolkit.layout.dimension import Dimension
from rich.cells import cell_len
from rich.console import Console
from rich.prompt import Confirm, Prompt

STYLE = get_style(
    {
        "questionmark": "#38bdf8",
        "pointer": "#38bdf8",
        "answer": "#38bdf8",
        "question": "bold",
        "fuzzy_border": "#64748b",
    },
    style_override=False,
)


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def fit_prompt(prompt, labels: list[str]):
    """Constrain the prompt to its labels, while allowing terminal resizing."""
    layout = prompt.application.layout
    if isinstance(layout, Layout):
        preferred = max(24, max((cell_len(label) for label in labels), default=0) + 8)

        def dimensions():
            width = min(shutil.get_terminal_size().columns, preferred)
            return Dimension(preferred=width, max=width)

        prompt.choice_window.height = lambda: Dimension(
            min=1,
            max=max(
                1,
                min(
                    prompt.content_control.choice_count,
                    shutil.get_terminal_size().lines // 2,
                ),
            ),
        )
        layout.container = VSplit(
            [
                HSplit(
                    [layout.container],
                    width=dimensions,
                )
            ],
            align=HorizontalAlign.LEFT,
        )
    return prompt


def choose(message: str, choices: list[tuple[str, str]], *, multiple=False) -> Any:
    if not interactive():
        raise click.ClickException(
            "This selection needs a terminal. Use a direct command or pass --task."
        )
    try:
        prompt = inquirer.fuzzy(
            message=message,
            choices=[Choice(value=value, name=label) for value, label in choices],
            multiselect=multiple,
            long_instruction=(
                "Search · Tab select\nEnter · Ctrl+C cancel"
                if multiple
                else "Type to search · ↑↓ move\nEnter · Ctrl+C cancel"
            ),
            style=STYLE,
            max_height="60%",
            border=True,
            validate=lambda value: bool(value),
            invalid_message="Select at least one item.",
        )
        result = fit_prompt(prompt, [label for _, label in choices]).execute()
    except (KeyboardInterrupt, EOFError) as exc:
        raise click.Abort() from exc
    if not result:
        raise click.Abort()
    return result


def ask(console: Console, label: str, *, default=None, password=False) -> str:
    if not interactive():
        return Prompt.ask(label, console=console, default=default, password=password)
    try:
        prompt = inquirer.secret if password else inquirer.text
        return prompt(
            message=label.strip(),
            default=default or "",
            instruction="Enter continue · Ctrl+C cancel",
            style=STYLE,
        ).execute()
    except (KeyboardInterrupt, EOFError) as exc:
        raise click.Abort() from exc


def ask_directory(console: Console, *, default: str) -> str:
    """Offer server-side directory completion when entering a path directly."""
    if not interactive():
        return ask(console, "Parent directory", default=default)
    try:
        return inquirer.filepath(
            message="Directory path",
            default=default,
            only_directories=True,
            instruction="Tab complete · Enter open · Ctrl+C cancel",
            style=STYLE,
        ).execute()
    except (KeyboardInterrupt, EOFError) as exc:
        raise click.Abort() from exc


def confirm(console: Console, label: str, *, default=False) -> bool:
    if not interactive():
        return Confirm.ask(label, console=console, default=default)
    try:
        return inquirer.confirm(message=label, default=default, style=STYLE).execute()
    except (KeyboardInterrupt, EOFError) as exc:
        raise click.Abort() from exc
