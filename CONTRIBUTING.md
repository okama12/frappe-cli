# Contributing to Frappe Installer CLI

Thank you for your interest in contributing! Here’s how to help make this CLI even better:

## Getting Started
- Fork the repository and clone it locally.
- Create a virtual environment and install dependencies:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install --editable .
  pip install -r requirements-dev.txt
  ```
- Run tests to verify your environment:
  ```bash
  pytest
  ```

## Code Style
- Use `black` for formatting, `flake8` for linting, and `isort` for imports.
- Keep commands modular: one file/module per command group.
- Add or update tests for new features and bugfixes.

## Making a Pull Request
- Branch from `main` and submit a pull request (PR).
- Describe your changes clearly.
- Ensure all CI checks pass before requesting review.

## Reporting Issues
- Use the GitHub Issues tab for bugs or feature requests.
- Please provide steps to reproduce and your environment details.

## License
By contributing, you agree your contributions will be licensed under the MIT License.
