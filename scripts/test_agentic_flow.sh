#!/usr/bin/env bash
# Run .agent-specific adapter tests only

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🧪 Running agentic flow tests..."
PYTEST_ADDOPTS="--no-cov" poetry run pytest quickscale_core/tests/test_agentic_flow_adapters.py -q

echo "✅ Agentic flow tests passed"
