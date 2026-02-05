#!/usr/bin/env bash
# Generate all platform configurations from .agent/ source files
# Usage: .agent/adapters/generate-all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

echo "🤖 Agentic Flow - Platform Configuration Generator"
echo "=================================================="
echo ""

# Check dependencies
check_deps() {
    local missing=()
    for cmd in bash cat sed grep; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "❌ Missing dependencies: ${missing[*]}"
        exit 1
    fi
}

check_deps

# Generate Claude Code configuration
generate_claude() {
    echo "📘 Generating Claude Code configuration..."

    if [[ -f "$SCRIPT_DIR/claude-adapter.sh" ]]; then
        bash "$SCRIPT_DIR/claude-adapter.sh"
        echo "   ✅ CLAUDE.md generated"
    else
        echo "   ⚠️  claude-adapter.sh not found, skipping"
    fi
}

# Generate Gemini CLI configuration
generate_gemini() {
    echo "💜 Generating Gemini CLI configuration..."

    if [[ -f "$SCRIPT_DIR/gemini-adapter.sh" ]]; then
        bash "$SCRIPT_DIR/gemini-adapter.sh"
        echo "   ✅ GEMINI.md generated"
    else
        echo "   ⚠️  gemini-adapter.sh not found, skipping"
    fi
}

# Generate GitHub Copilot configuration
generate_copilot() {
    echo "🐙 Generating GitHub Copilot configuration..."

    if [[ -f "$SCRIPT_DIR/copilot-adapter.sh" ]]; then
        bash "$SCRIPT_DIR/copilot-adapter.sh"
        echo "   ✅ .github/copilot-instructions.md generated"
    else
        echo "   ⚠️  copilot-adapter.sh not found, skipping"
    fi
}

# Main execution
main() {
    echo "Source: $AGENT_DIR"
    echo "Output: $ROOT_DIR"
    echo ""

    generate_claude
    generate_gemini
    generate_copilot

    echo ""
    echo "=================================================="
    echo "✅ Platform configurations generated successfully!"
    echo ""
    echo "Generated files:"
    [[ -f "$ROOT_DIR/CLAUDE.md" ]] && echo "  - CLAUDE.md"
    [[ -f "$ROOT_DIR/GEMINI.md" ]] && echo "  - GEMINI.md"
    [[ -f "$ROOT_DIR/.github/copilot-instructions.md" ]] && echo "  - .github/copilot-instructions.md"
    echo ""
    echo "Run this script after modifying .agent/ files to update configs."
}

main "$@"
