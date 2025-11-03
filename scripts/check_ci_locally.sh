#!/usr/bin/env bash
set -euo pipefail

# Local CI check script — run this before committing to verify the same steps
# as GitHub Actions (install + lint + typecheck + package tests).

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

echo "[ci-local] Installing dependencies (may take a few minutes)"
poetry install --with dev

echo "[ci-local] Running ruff (lint)"
poetry run ruff check quickscale_core quickscale_cli
echo "Running ruff format on quickscale_core..."
poetry run ruff format quickscale_core
echo "Running ruff format on quickscale_cli..."
poetry run ruff format quickscale_cli
echo "Checking format..."
poetry run ruff format --check quickscale_core quickscale_cli

echo "[ci-local] Running mypy (type checks)"
poetry run mypy quickscale_core/src/ quickscale_cli/src/

echo "[ci-local] Running quickscale_core tests (unit + integration)"
poetry run pytest quickscale_core -m "not e2e" --cov=quickscale_core --cov-report=term

echo "[ci-local] Running quickscale_cli tests"
poetry run pytest quickscale_cli --cov=quickscale_cli --cov-report=term

echo "[ci-local] All checks passed"
