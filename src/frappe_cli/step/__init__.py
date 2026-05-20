"""`fp step` — run any individual wizard step as a standalone command.

Each command thinly wraps an `InstallStep` subclass (the same code the
`fp install wizard` runs end-to-end) so behaviour — self-healing,
verification, dry-run, rollback hooks — stays consistent between the
automated wizard and ad-hoc / partial reruns.

Examples:
    fp step list                                       # show every step
    fp step dns-multitenant --bench-name test5-bench
    fp step production --bench-name test5-bench
    fp step ssl --bench-name test5-bench --site-name test5.example.com
    fp step site-create --bench-name my-bench --site-name my.example.com
"""

import click

from .commands import ALL_STEP_COMMANDS, list_steps


@click.group(name="step")
def step() -> None:
    """Run any individual wizard step independently of `install wizard`.

    Every step is the same class the wizard runs, so `check()` skips work
    that is already done and self-healing/verification behaviour is identical.
    """


step.add_command(list_steps)
for cmd in ALL_STEP_COMMANDS:
    step.add_command(cmd)
