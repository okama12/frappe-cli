"""Unit tests for interactive site picker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_pick_site_interactive_returns_selected_value():
    from frappe_cli.dev.site_picker import pick_site_interactive

    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = "staging.example.com"

    with patch("frappe_cli.dev.site_picker.inquirer.fuzzy", return_value=mock_prompt) as fuzzy:
        result = pick_site_interactive(
            ["dev.local", "staging.example.com"],
            active="dev.local",
        )

    assert result == "staging.example.com"
    fuzzy.assert_called_once()
    kwargs = fuzzy.call_args.kwargs
    assert kwargs["message"]
    # choices must be non-empty and preserve site values
    assert len(kwargs["choices"]) == 2


def test_pick_site_interactive_raises_abort_on_keyboard_interrupt():
    from frappe_cli.dev.site_picker import pick_site_interactive
    import click

    mock_prompt = MagicMock()
    mock_prompt.execute.side_effect = KeyboardInterrupt

    with patch("frappe_cli.dev.site_picker.inquirer.fuzzy", return_value=mock_prompt):
        with pytest.raises(click.Abort):
            pick_site_interactive(["dev.local"], active=None)


def test_pick_site_interactive_raises_abort_on_none_result():
    from frappe_cli.dev.site_picker import pick_site_interactive
    import click

    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = None

    with patch("frappe_cli.dev.site_picker.inquirer.fuzzy", return_value=mock_prompt):
        with pytest.raises(click.Abort):
            pick_site_interactive(["dev.local"], active=None)


def test_pick_site_interactive_rejects_empty_sites():
    from frappe_cli.dev.site_picker import pick_site_interactive
    import click

    with pytest.raises(click.ClickException, match="No sites"):
        pick_site_interactive([], active=None)
