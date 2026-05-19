import importlib.metadata

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def print_header(console: Console) -> None:
    try:
        version = importlib.metadata.version("frappe-cli")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    content = Text()
    content.append("  Frappe CLI  ", style="bold green")
    content.append(f"v{version}\n", style="bold")
    content.append("  Production Server Installer", style="dim")
    console.print(Panel(content, box=box.ROUNDED, padding=(1, 2)))


def print_success(console: Console, ctx) -> None:
    protocol = "http" if ctx.skip_ssl else "https"
    ssl_line = (
        "  [dim]SSL[/dim]      Let's Encrypt — auto-renews"
        if not ctx.skip_ssl
        else "  [dim]SSL[/dim]      Not configured (--skip-ssl)"
    )
    app_line = (
        f"  [dim]App[/dim]      {ctx.app_name}  ({ctx.app_branch})"
        if ctx.app_url
        else "  [dim]App[/dim]      Frappe only"
    )
    lines = "\n".join(
        [
            f"[bold green]✓  Frappe is live at {protocol}://{ctx.site_name}[/bold green]\n",
            f"  [dim]Bench[/dim]    ~/{ctx.bench_name}",
            f"  [dim]Site[/dim]     {ctx.site_name}",
            app_line,
            ssl_line,
        ]
    )
    console.print(
        Panel(lines, title="[green]Installation Complete[/green]", box=box.ROUNDED)
    )
    console.print("\n  [dim]Next steps:[/dim]")
    console.print("    [cyan]frappe service status[/cyan]   — check running services")
    console.print("    [cyan]frappe site backup[/cyan]      — take a manual backup")
    if ctx.skip_ssl:
        console.print(
            "    [cyan]frappe install wizard[/cyan]   — re-run without --skip-ssl to add SSL\n"
        )
    else:
        console.print(
            "    [cyan]frappe ssl setup[/cyan]        — renew SSL certificate\n"
        )


def print_error(
    console: Console, step_description: str, message: str, hint: str = ""
) -> None:
    parts = [f"[red]{message}[/red]"]
    if hint.strip():
        parts.append(f"\n  [dim]stderr:[/dim] {hint.strip()[:300]}")
    parts.append("\n  Fix the issue then re-run:")
    parts.append("    [cyan]frappe install wizard --resume[/cyan]")
    console.print(
        Panel(
            "\n".join(parts),
            title=f"[bold red]Error in: {step_description}[/bold red]",
            box=box.ROUNDED,
        )
    )
