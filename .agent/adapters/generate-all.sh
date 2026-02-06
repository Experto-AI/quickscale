#!/usr/bin/env bash
# Generate all platform configurations from .agent/ source files
#
# Supported platforms:
#   - Claude Code    → CLAUDE.md, .claude/commands/, .claude/agents/
#   - Gemini CLI     → GEMINI.md, .gemini/commands/, .gemini/settings.json
#   - GitHub Copilot → .github/copilot-instructions.md, prompts/, agents/, instructions/
#   - Codex CLI      → AGENTS.md, .codex/config.toml
#   - OpenCode       → .opencode.json, .opencode/commands/
#
# Usage: .agent/adapters/generate-all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

echo "🤖 Agentic Flow — Platform Configuration Generator"
echo "=================================================="
echo ""

# Check dependencies
check_deps() {
    local missing=()
    for cmd in bash cat sed grep awk; do
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

# Run an adapter script if it exists
run_adapter() {
    local name="$1" script="$2"
    if [[ -f "$SCRIPT_DIR/$script" ]]; then
        bash "$SCRIPT_DIR/$script"
    else
        echo "  ⚠️  $script not found, skipping $name"
    fi
}

# Main execution
main() {
    echo "Source: $AGENT_DIR"
    echo "Output: $ROOT_DIR"
    echo ""

    run_adapter "Claude Code"    "claude-adapter.sh"
    echo ""
    run_adapter "Gemini CLI"     "gemini-adapter.sh"
    echo ""
    run_adapter "GitHub Copilot" "copilot-adapter.sh"
    echo ""
    run_adapter "Codex CLI"      "codex-adapter.sh"
    echo ""
    run_adapter "OpenCode"       "opencode-adapter.sh"

    echo ""
    echo "=================================================="
    echo "✅ All platform configurations generated!"
    echo ""
    echo "Generated files:"
    # Claude Code
    [[ -f "$ROOT_DIR/CLAUDE.md" ]]                         && echo "  📘 CLAUDE.md"
    [[ -d "$ROOT_DIR/.claude/commands" ]]                  && echo "  📘 .claude/commands/"
    [[ -d "$ROOT_DIR/.claude/agents" ]]                    && echo "  📘 .claude/agents/"
    # Gemini CLI
    [[ -f "$ROOT_DIR/GEMINI.md" ]]                         && echo "  💜 GEMINI.md"
    [[ -d "$ROOT_DIR/.gemini/commands" ]]                  && echo "  💜 .gemini/commands/"
    [[ -f "$ROOT_DIR/.gemini/settings.json" ]]             && echo "  💜 .gemini/settings.json"
    # GitHub Copilot
    [[ -f "$ROOT_DIR/.github/copilot-instructions.md" ]]   && echo "  🐙 .github/copilot-instructions.md"
    [[ -d "$ROOT_DIR/.github/prompts" ]]                   && echo "  🐙 .github/prompts/"
    [[ -d "$ROOT_DIR/.github/agents" ]]                    && echo "  🐙 .github/agents/"
    [[ -d "$ROOT_DIR/.github/instructions" ]]              && echo "  🐙 .github/instructions/"
    # Codex CLI
    [[ -f "$ROOT_DIR/AGENTS.md" ]]                         && echo "  🤖 AGENTS.md"
    [[ -f "$ROOT_DIR/.codex/config.toml" ]]                && echo "  🤖 .codex/config.toml"
    # OpenCode
    [[ -f "$ROOT_DIR/.opencode.json" ]]                    && echo "  📦 .opencode.json"
    [[ -d "$ROOT_DIR/.opencode/commands" ]]                && echo "  📦 .opencode/commands/"
    echo ""
    echo "Run this script after modifying .agent/ files to update all configs."
    echo "For specifications, see: .agent/SOURCES.md"
}

main "$@"
