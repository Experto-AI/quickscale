#!/usr/bin/env bash
# Install QuickScale globally from the codebase

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "🚀 Installing QuickScale globally..."

# Build quickscale_core first
echo "📦 Building quickscale_core..."
cd "$ROOT/quickscale_core"
rm -rf dist/
poetry build

# Build quickscale_cli
echo "📦 Building quickscale_cli..."
cd "$ROOT/quickscale_cli"
rm -rf dist/
poetry build

# Install both packages globally
echo "📦 Installing globally with pip..."
pip install "$ROOT/quickscale_core/dist/quickscale_core-"*.whl
pip install "$ROOT/quickscale_cli/dist/quickscale_cli-"*.whl

echo "✅ QuickScale installed globally. You can now run 'quickscale' from any directory."