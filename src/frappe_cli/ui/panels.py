import importlib.metadata

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Keep borders close to their contents.
_COMPACT_PAD = (0, 1)


def _fit_panel(
    renderable, *, title: str | Text | None = None, border_style: str | None = None
):
    return Panel.fit(
        renderable,
        box=box.ROUNDED,
        padding=_COMPACT_PAD,
        title=title,
        border_style=border_style,
    )


_ASCII_ART = """\
[bold green]  ███████╗██████╗  █████╗ ██████╗ ██████╗ ███████╗     ██████╗██╗     ██╗[/bold green]
[bold green]  ██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝    ██╔════╝██║     ██║[/bold green]
[bold green]  █████╗  ██████╔╝███████║██████╔╝██████╔╝█████╗      ██║     ██║     ██║[/bold green]
[bold green]  ██╔══╝  ██╔══██╗██╔══██║██╔═══╝ ██╔═══╝ ██╔══╝      ██║     ██║     ██║[/bold green]
[bold green]  ██║     ██║  ██║██║  ██║██║     ██║     ███████╗    ╚██████╗███████╗██║[/bold green]
[bold green]  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚══════╝     ╚═════╝╚══════╝╚═╝[/bold green]\
"""


def print_header(console: Console) -> None:
    context = click.get_current_context(silent=True)
    if context:
        if context.meta.get("header_shown"):
            return
        context.meta["header_shown"] = True
    try:
        version = importlib.metadata.version("frappe-cli")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    console.print()
    console.print(_ASCII_ART)
    console.print(Text.assemble(("Frappe CLI", "bold cyan"), (f"  {version}", "dim")))
    console.print("Install · Operate · Develop", style="dim")
    console.print("Rashidi Okama · Tanzania", style="dim")
    console.print("github.com/okama12 · rashidiokama.com", style="dim")


def print_plan(console: Console, ctx, steps, *, completed=None) -> None:
    import getpass
    import shutil

    from rich.table import Table

    completed = completed or set()
    details = Text(f"Owner: {getpass.getuser()}\n")
    if ctx.bench_name:
        details.append(f"Bench: {ctx.bench_path}\n")
    if ctx.site_name:
        details.append(f"Site: {ctx.site_name}\n")
    details.append(f"System: Ubuntu {ctx.ubuntu_version}")
    if ctx.dry_run:
        details.append("\nPreview only · no commands or state changes", style="yellow")
    console.print(_fit_panel(details, title="Setup plan", border_style="cyan"))
    table = Table(box=None, expand=False, padding=(0, 1))
    table.add_column("Component", ratio=2)
    table.add_column("Detected / planned action", ratio=2)
    binaries = {
        "uv_check": "uv",
        "bench_install": "bench",
        "nodejs": "node",
        "redis": "redis-server",
        "wkhtmltopdf": "wkhtmltopdf",
    }
    for step in steps:
        status = "Check, then configure if needed"
        if step.name in completed:
            status = "Saved completion · revalidate when supported"
        elif step.name in binaries and shutil.which(binaries[step.name]):
            status = "Found · verify requirements"
        elif (
            step.name == "bench_init" and (ctx.bench_path / "apps" / "frappe").is_dir()
        ):
            status = "Found · reuse existing bench"
        elif (
            step.name == "site_create"
            and (
                ctx.bench_path / "sites" / ctx.site_name / "site_config.json"
            ).is_file()
        ):
            status = "Found · reuse existing site"
        elif (
            step.name in {"app_get", "app_install", "bench_restart"} and not ctx.app_url
        ):
            status = "Skip · no app selected"
        table.add_row(Text(step.description), Text(status, style="dim"))
    console.print(table)


def print_success(console: Console, ctx) -> None:
    protocol = "http" if ctx.skip_ssl else "https"
    ssl_line = (
        "[dim]SSL[/dim]     Let's Encrypt — auto-renews"
        if not ctx.skip_ssl
        else "[dim]SSL[/dim]     Not configured (--skip-ssl)"
    )
    app_line = (
        f"[dim]App[/dim]     {ctx.app_name} ({ctx.app_branch})"
        if ctx.app_url
        else "[dim]App[/dim]     Frappe only"
    )
    body = "\n".join(
        [
            f"[bold green]✓ Setup complete · {protocol}://{ctx.site_name}[/bold green]",
            f"[dim]Bench[/dim]   {ctx.bench_path}",
            f"[dim]Site[/dim]    {ctx.site_name}",
            app_line,
            ssl_line,
        ]
    )
    console.print(
        _fit_panel(
            body, title="[green]Installation Complete[/green]", border_style="green"
        )
    )
    console.print("\n[dim]Next steps:[/dim]")
    console.print("  [cyan]fp status[/cyan]  — check running services")
    console.print("  [cyan]fp backup[/cyan]  — take a manual backup")
    if ctx.skip_ssl:
        console.print(f"  [cyan]fp ssl {ctx.site_name}[/cyan]  — configure HTTPS")
    else:
        console.print(
            f"  [cyan]fp ssl {ctx.site_name}[/cyan]  — inspect or configure HTTPS"
        )
    console.print(
        "\n[dim]Made with care by Rashidi Okama in Tanzania · "
        "if this saved you time, star the repo:[/dim] "
        "[cyan]github.com/okama12/frappe-cli[/cyan]"
    )


def print_error(
    console: Console, step_description: str, message: str, hint: str = ""
) -> None:
    body = Text(message, style="red")
    if hint.strip():
        body.append("\n\nDetails\n", style="bold")
        body.append(hint.strip(), style="dim")
    body.append(
        "\n\nProgress is preserved. Correct the issue, then run:\n", style="white"
    )
    body.append("fp setup --resume", style="bold cyan")
    console.print(
        _fit_panel(
            body, title=Text(f"Stopped · {step_description}"), border_style="red"
        )
    )
