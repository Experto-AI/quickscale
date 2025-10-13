#!/usr/bin/env bash
# Install QuickScale globally from the codebase

set -e

echo "🚀 Installing QuickScale globally..."

# Build the package
echo "📦 Building quickscale package..."
cd quickscale
rm -rf dist/
poetry build

# Install globally
echo "📦 Installing globally with pip..."
pip install dist/quickscale-*.whl

echo "✅ QuickScale installed globally. You can now run 'quickscale' from any directory."