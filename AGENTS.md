# Repository guidance

## Project

`frappe-cli` is a Python CLI for installing and managing Frappe/ERPNext and
running daily bench commands. It uses Click, Rich, PyYAML, and InquirerPy.
Python >=3.10 is required; CI covers Python 3.10, 3.11, and 3.12.
The package uses Poetry and a `src/` layout.

The installed command is `fp`; `fcli` is a compatibility alias. Both point to
`frappe_cli.cli:cli`. Use `fp --help` and `fp version` for local inspection.

## Development commands

Run from the repository root:

```bash
poetry install
PYTHONPATH=src poetry run pytest tests/
PYTHONPATH=src poetry run pytest tests/test_cli_basic.py
PYTHONPATH=src poetry run pytest tests/test_cli_basic.py::test_frappe_help
PYTHONPATH=src poetry run pytest --cov=src tests/
poetry run ruff check src/ tests/
poetry run black --check src/ tests/
poetry run isort --check-only src/ tests/
poetry run mypy src tests
```

`poetry run bash scripts/lint.sh` runs repository-wide Ruff, Black, isort,
and mypy checks. Configuration lives in `pyproject.toml`: four-space indentation,
88-character lines, Black formatting, and Black-compatible import ordering.
Prefer the manifest and CI workflows over older setup examples in documentation;
there is no `requirements-dev.txt`, and the configured linter is Ruff.

## Code map

- `src/frappe_cli/cli.py`: root Click group, command registration, and aliases.
- Command directories such as `site/`, `ssl/`, `service/`, and `backup/`:
  Click groups in `__init__.py` and individual command modules.
- `dev/`: bench command passthroughs, site picker, sudo commands, and bench/site
  context. The active site lives in `<bench_root>/.fp.yaml`.
- `install/wizard.py`, `install/context.py`, and `install/state.py`: wizard
  orchestration, shared context, and resumable progress. Wizard state lives in
  `~/.frappe-cli-state.json`, separately from the active-site context.
- `install/steps/`: ordered installation pipeline defined by `ALL_STEPS` in
  `__init__.py`. `InstallStep.check()` returns true when already complete;
  `run()` performs the step; `rollback()` provides best-effort cleanup.
- `step/`: standalone commands exposing the wizard's installation steps.
- `utils/`: shell execution, errors, logging, validators, SSL, Git, and sudoers
  helpers. Installation steps use the execution helpers on `InstallStep`.
- `ui/`: Rich progress rendering, prompts, and summary panels.
- `tests/`: pytest tests, generally grouped by command or shared component.
- `src/frappe_cli/data/example_config.yaml`: example configuration. The root
  CLI's `--config` loading is currently stubbed; do not assume it populates context.

## Implementation and verification

Follow existing Click registration and shared-helper patterns. Keep wizard steps
reusable through both the wizard and `fp step`, preserve resume behavior, and
respect existing dry-run handling when changing command execution.

Test CLI behavior with `click.testing.CliRunner`. Mock subprocesses and external
services, and use temporary directories for bench/site fixtures. Installer and
operations commands can change packages, databases, services, firewall rules,
and certificates; verification should use isolated fixtures instead of running
them against the host.

Run focused tests for the affected behavior and the relevant formatting, lint,
and type checks. Use the full suite for changes spanning shared components.
Keep user-facing command documentation consistent with behavior changes.
Do not include credentials, runtime logs, local state, or generated caches in
commits.
