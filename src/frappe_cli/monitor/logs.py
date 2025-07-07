import click

@click.command()
@click.option('--service', help='Service to tail logs for (e.g. nginx, supervisor)')
@click.option('--tail', default=100, help='Number of log lines to show')
def logs(service, tail):
    """Show live logs for a service (stub)."""
    click.secho(f"[STUB] Would show last {tail} lines of logs for service '{service}'. Not yet implemented.", fg="yellow") 