"""Interactive site selection for ``fp use``."""

from __future__ import annotations

from typing import Optional

import click
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from frappe_cli.ui.terminal import fit_prompt


def pick_site_interactive(sites: list[str], active: Optional[str] = None) -> str:
    """Prompt the user to pick a site with fuzzy search.

    Returns the selected site name. Raises ``click.Abort`` if the user
    cancels (Ctrl+C) or the prompt returns no value. Raises
    ``click.ClickException`` if *sites* is empty.
    """
    if not sites:
        raise click.ClickException("No sites found in this bench.")

    choices = [
        Choice(
            value=site,
            name=f"● {site}" if active and site == active else f"  {site}",
        )
        for site in sites
    ]

    try:
        prompt = inquirer.fuzzy(
            message="Select site:",
            choices=choices,
            long_instruction="Type to filter · ↑↓ move\nEnter · Ctrl+C cancel",
            border=True,
        )
        result = fit_prompt(prompt, [choice.name for choice in choices]).execute()
    except KeyboardInterrupt as exc:
        raise click.Abort() from exc

    if not result:
        raise click.Abort()

    return str(result)
