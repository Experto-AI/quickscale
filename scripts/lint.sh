#!/usr/bin/env bash
# Run standardized Python lint and type checks through the root Makefile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "🔍 Running standardized Python quality checks..."
echo ""

echo "📦 Applying Ruff auto-fixes through Poetry-managed Make targets..."
make lint-fix -- --core --cli --modules

echo ""
echo "📦 Running MyPy through Poetry-managed Make targets..."
make typecheck -- --core --cli --modules

echo ""
echo "✅ All Python quality checks passed!"
echo ""
echo "💡 Preferred maintainer commands:"
echo "   make lint -- --core --cli --modules        # check only"
echo "   make lint-fix -- --core --cli --modules    # auto-fix"
echo "   make typecheck -- --core --cli --modules   # type checking"
