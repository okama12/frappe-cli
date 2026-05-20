import importlib.metadata

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Tight padding so panels hug their content (wizard list/output panels unchanged).
_COMPACT_PAD = (0, 1)


def _fit_panel(
    renderable, *, title: str | None = None, border_style: str | None = None
):
    return Panel.fit(
        renderable,
        box=box.ROUNDED,
        padding=_COMPACT_PAD,
        title=title,
        border_style=border_style,
    )


def print_header(console: Console) -> None:
    try:
        version = importlib.metadata.version("frappe-cli")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    content = Text()
    content.append("Frappe CLI ", style="bold green")
    content.append(f"v{version}\n", style="bold")
    content.append("Production Server Installer\n", style="dim")
    content.append("Built by ", style="dim")
    content.append("Rashidi Okama", style="bold cyan")
    content.append(" · Tanzania\n", style="dim")
    content.append("github.com/okama12", style="cyan")
    content.append(" · ", style="dim")
    content.append("rashidiokama.com", style="cyan")
    console.print(_fit_panel(content, border_style="green"))


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
            f"[bold green]✓ Frappe is live at {protocol}://{ctx.site_name}[/bold green]",
            f"[dim]Bench[/dim]   ~/{ctx.bench_name}",
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
    console.print("  [cyan]fp service status[/cyan]  — check running services")
    console.print("  [cyan]fp site backup[/cyan]     — take a manual backup")
    if ctx.skip_ssl:
        console.print(
            "  [cyan]fp install wizard[/cyan]  — re-run without --skip-ssl to add SSL"
        )
    else:
        console.print("  [cyan]fp ssl setup[/cyan]       — renew SSL certificate")
    console.print(
        "\n[dim]Made with care by Rashidi Okama in Tanzania · "
        "if this saved you time, star the repo:[/dim] "
        "[cyan]github.com/okama12/frappe-cli[/cyan]"
    )


def print_error(
    console: Console, step_description: str, message: str, hint: str = ""
) -> None:
    parts = [f"[red]{message}[/red]"]
    if hint.strip():
        parts.append(f"\n[dim]stderr:[/dim] {hint.strip()[:300]}")
    parts.append("\nFix the issue then re-run:")
    parts.append("  [cyan]fp install wizard --resume[/cyan]")
    console.print(
        _fit_panel(
            "\n".join(parts),
            title=f"[bold red]Error: {step_description}[/bold red]",
            border_style="red",
        )
    )
