#!/bin/bash
# Run linting checks on the codebase

set -e

echo "Running Ruff linter..."
ruff check .

echo "Running Black formatter check..."
black --check .

echo "Running isort check..."
isort --check .

echo "Running mypy type checker..."
mypy src tests

echo "All checks passed!"