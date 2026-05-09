#!/usr/bin/env bash
# Render a showcase_react starter and prove its frontend toolchain without Docker.
#
# Usage: ./scripts/frontend_proof.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Running rendered showcase_react frontend proof..."
echo ""

if ! command -v poetry &> /dev/null; then
	echo "❌ Poetry is required but not installed."
	exit 1
fi

if ! command -v node &> /dev/null; then
	echo "❌ Node.js is required but not installed."
	echo "   Install Node.js 24+ from https://nodejs.org/"
	exit 1
fi

NODE_VERSION=$(node --version | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 24 ]; then
	echo "❌ Node.js 24+ is required (found $(node --version))"
	exit 1
fi

if ! command -v pnpm &> /dev/null; then
	echo "❌ pnpm is required but not installed."
	echo "   Install pnpm: npm install -g pnpm"
	exit 1
fi

mkdir -p "$ROOT/.quickscale"
WORK_DIR="$(mktemp -d "$ROOT/.quickscale/frontend-proof-XXXXXX")"
PROJECT_NAME="frontend-proof"
PROJECT_DIR="$WORK_DIR/$PROJECT_NAME"
FRONTEND_DIR="$PROJECT_DIR/frontend"

cleanup() {
	status=$?
	if [ "$status" -eq 0 ]; then
		rm -rf "$WORK_DIR"
	else
		echo ""
		echo "⚠️ Proof workspace preserved for inspection: $WORK_DIR"
	fi
	exit "$status"
}
trap cleanup EXIT

echo "📦 Rendering showcase_react starter..."
QUICKSCALE_FRONTEND_PROOF_DIR="$PROJECT_DIR" \
QUICKSCALE_FRONTEND_PROOF_NAME="$PROJECT_NAME" \
	poetry run python - <<'PY'
import os
from pathlib import Path

from quickscale_core.generator import ProjectGenerator

project_name = os.environ["QUICKSCALE_FRONTEND_PROOF_NAME"]
project_dir = Path(os.environ["QUICKSCALE_FRONTEND_PROOF_DIR"])

ProjectGenerator(theme="showcase_react").generate(project_name, project_dir)
PY

if [ ! -d "$FRONTEND_DIR" ]; then
	echo "❌ Generated frontend directory not found: $FRONTEND_DIR"
	exit 1
fi

echo "  ✅ Starter rendered to $PROJECT_DIR"
echo ""

cd "$FRONTEND_DIR"

echo "📦 Running pnpm install..."
pnpm install
echo ""

echo "🔍 Running pnpm type-check..."
pnpm type-check
echo ""

echo "🏗️ Running pnpm build..."
pnpm build
echo ""

echo "✅ Rendered showcase_react frontend proof passed!"
