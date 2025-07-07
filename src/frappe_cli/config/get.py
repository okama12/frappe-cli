import click

@click.command()
@click.argument('key')
def get(key):
    """Get a config value (stub)."""
    click.secho(f"[STUB] Would get config key '{key}'. Not yet implemented.", fg="yellow") 