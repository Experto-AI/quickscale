#!/usr/bin/env bash
# Lint and statically validate the .agent transpiler system

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="$ROOT_DIR/.agent"

if [[ ! -d "$AGENT_DIR" ]]; then
  echo "ERROR: .agent directory not found"
  exit 1
fi

echo "🔍 Linting agentic flow system..."

echo "  → Validating adapter shell syntax"
while IFS= read -r script; do
  bash -n "$script"
done < <(find "$AGENT_DIR/adapters" -type f -name '*.sh' | sort)

echo "  → Validating JSON files"
while IFS= read -r json_file; do
  jq -e . "$json_file" > /dev/null
done < <(find "$AGENT_DIR" -type f -name '*.json' | sort)

echo "  → Building IR"
TMP_IR="$(mktemp)"
trap 'rm -f "$TMP_IR"' EXIT
bash "$AGENT_DIR/adapters/build-ir.sh" "$TMP_IR" > /dev/null

echo "  → Checking IR required fields"
jq -e '
  .schema_version
  and .generated_at
  and .config
  and .agents
  and .subagents
  and .skills
  and .workflows
  and .contexts
  and .diagnostics
' "$TMP_IR" > /dev/null

echo "  → Checking capability declaration completeness"
for capability in "$AGENT_DIR"/adapters/capabilities/*.yaml; do
  grep -q '^platform:' "$capability"
  grep -q '^verified_on:' "$capability"
  grep -q '^tier:' "$capability"
  grep -q '^supports:' "$capability"
done

echo "✅ Agentic flow lint checks passed"
