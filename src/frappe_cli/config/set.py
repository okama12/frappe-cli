import click

@click.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set a config value (stub)."""
    click.secho(f"[STUB] Would set config key '{key}' to '{value}'. Not yet implemented.", fg="yellow") 