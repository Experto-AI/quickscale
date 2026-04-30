#!/usr/bin/env bash
# Lint .agent shell scripts for syntax errors.
# Usage: ./scripts/lint_agentic_flow.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT_DIR="$ROOT/.agent"

echo "🔍 Running .agent shell lint..."
echo ""

if [ ! -d "$AGENT_DIR" ]; then
	echo "ℹ️ No .agent directory found. Skipping agent shell lint."
	exit 0
fi

mapfile -d '' SHELL_FILES < <(find "$AGENT_DIR" -type f -name "*.sh" -print0 | sort -z)

if [ "${#SHELL_FILES[@]}" -eq 0 ]; then
	echo "ℹ️ No .agent shell scripts found. Skipping agent shell lint."
	exit 0
fi

echo "📦 Checking ${#SHELL_FILES[@]} .agent shell script(s)..."

for script_path in "${SHELL_FILES[@]}"; do
	interpreter="bash"
	if IFS= read -r first_line < "$script_path" && [[ "$first_line" == "#!"* ]] && [[ "$first_line" != *"bash"* ]]; then
		interpreter="sh"
	fi

	echo "  → ${script_path#"$ROOT/"}"
	"$interpreter" -n "$script_path"
done

echo ""
echo "✅ .agent shell lint passed!"
