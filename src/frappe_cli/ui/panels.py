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
    lines = "\n".join(
        [
            f"[bold green]✓  Frappe is live at https://{ctx.site_name}[/bold green]\n",
            f"  [dim]Bench[/dim]    ~/{ctx.bench_name}",
            f"  [dim]Site[/dim]     {ctx.site_name}",
            f"  [dim]App[/dim]      {ctx.app_name}  ({ctx.app_branch})",
            "  [dim]SSL[/dim]      Let's Encrypt — auto-renews",
        ]
    )
    console.print(
        Panel(lines, title="[green]Installation Complete[/green]", box=box.ROUNDED)
    )
    console.print("\n  [dim]Next steps:[/dim]")
    console.print("    [cyan]frappe service status[/cyan]   — check running services")
    console.print("    [cyan]frappe site backup[/cyan]      — take a manual backup")
    console.print("    [cyan]frappe ssl setup[/cyan]        — renew SSL certificate\n")


def print_error(
    console: Console, step_description: str, message: str, hint: str = ""
) -> None:
    parts = [f"[red]{message}[/red]"]
    if hint.strip():
        parts.append(f"\n  [dim]stderr:[/dim] {hint.strip()[:300]}")
    parts.append("\n  Fix the issue then re-run:")
    parts.append("    [cyan]frappe install --resume[/cyan]")
    console.print(
        Panel(
            "\n".join(parts),
            title=f"[bold red]Error in: {step_description}[/bold red]",
            box=box.ROUNDED,
        )
    )
