import click

@click.command()
def health():
    """Show system health (stub)."""
    click.secho("[STUB] Would show system health. Not yet implemented.", fg="yellow") 