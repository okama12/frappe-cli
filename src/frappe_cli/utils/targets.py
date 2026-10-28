"""Shared bench/site resolution for direct commands and guided setup."""

from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from frappe_cli.dev.context import (
    discover_benches,
    find_bench_root,
    list_sites,
    read_active_site,
    site_exists,
    write_active_site,
)
from frappe_cli.ui import terminal
from frappe_cli.utils.errors import ValidationError
from frappe_cli.utils.validators import validate_bench_name, validate_site_name


def validated(value, validator):
    try:
        return validator(value)
    except ValidationError as exc:
        raise click.BadParameter(str(exc)) from exc


def bench_target(value: str | None = None) -> Path:
    current = find_bench_root(Path.cwd())
    if value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = current if current and current.name == value else Path.home() / path
    elif current:
        path = current
    elif terminal.interactive():
        benches = discover_benches()
        choices = [(str(path), str(path)) for path in benches]
        choices.append(("other", "Enter another bench path"))
        selected = terminal.choose("Select bench", choices)
        path = Path(
            terminal.ask(Console(), "Bench path") if selected == "other" else selected
        ).expanduser()
    else:
        raise click.ClickException(
            "No bench selected. Pass --bench PATH or run inside a bench."
        )
    path = path.resolve()
    validated(path.name, validate_bench_name)
    if not all((path / marker).is_dir() for marker in ("apps", "sites")):
        raise click.ClickException(f"No Frappe bench at {path}.")
    return path


def site_target(bench: Path, value: str | None = None) -> str:
    site = value or read_active_site(bench)
    if site:
        validated(site, validate_site_name)
        if site_exists(bench, site):
            return site
        raise click.ClickException(
            f"Site '{site}' does not exist in {bench}. Run fp use or pass --site."
        )
    if terminal.interactive():
        available = list_sites(bench)
        if available:
            selected = terminal.choose(
                "Select site", [(name, name) for name in available]
            )
            write_active_site(bench, selected)
            return selected
    raise click.ClickException("No active site. Run fp use or pass --site NAME.")


def print_target(console: Console, bench: Path, site: str = "") -> None:
    console.print(
        Text(f"Bench: {bench}" + (f" · Site: {site}" if site else ""), style="dim")
    )
