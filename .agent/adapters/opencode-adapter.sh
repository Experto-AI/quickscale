#!/usr/bin/env bash
# Generate OpenCode configuration from .agent/ source files
#
# ⚠️  DEPRECATION WARNING ⚠️
# OpenCode was archived in September 2025 and succeeded by Crush.
# This adapter is maintained for compatibility with existing installations ONLY.
# New projects should use Claude Code, Gemini CLI, GitHub Copilot, or Codex CLI.
#
# Creates:
#   - .opencode.json           — project configuration (agents, MCP, LSP)
#   - .opencode/commands/*.md  — custom commands (from .agent/workflows/)
#
# Leveraged OpenCode native features:
#   - .opencode.json for project-level config (agents, MCP servers, LSP)
#   - .opencode/commands/*.md for custom slash commands with $NAME args
#   - Built-in sub-agent tool for delegation
#
# Does NOT modify any .agent/ source files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# Output paths
OPENCODE_JSON="$ROOT_DIR/.opencode.json"
OPENCODE_DIR="$ROOT_DIR/.opencode"
COMMANDS_DIR="$OPENCODE_DIR/commands"

# Create output directories
mkdir -p "$COMMANDS_DIR"

# ─── Helpers ───────────────────────────────────────────────────────────────────

# Extract a scalar YAML frontmatter value.
get_frontmatter() {
    local file="$1" key="$2"
    [[ -f "$file" ]] || return 0
    sed -n '/^---$/,/^---$/p' "$file" \
        | grep "^${key}:" \
        | head -1 \
        | sed "s/^${key}:[[:space:]]*//" \
        | tr -d '"' \
        | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Extract body content after YAML frontmatter.
get_body() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$file"
}

# Escape string for JSON (simple: escape backslashes, quotes, newlines)
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

# ─── .opencode.json ───────────────────────────────────────────────────────────

generate_opencode_json() {
    # Build system prompt from project conventions
    local system_prompt
    system_prompt="You are a QuickScale development agent. QuickScale is a Django project generator for production-ready SaaS applications."
    system_prompt+="\\n\\nCode Standards: Python 3.11+, type hints on public APIs, Google-style docstrings, Ruff for linting, Poetry for packages."
    system_prompt+="\\n\\nPrinciples: SOLID, DRY, KISS. No bare except. No global mocking in tests."
    system_prompt+="\\n\\nTesting: pytest, test isolation mandatory, coverage >= 90% overall, >= 80% per file."
    system_prompt+="\\n\\nAlways run ./scripts/lint.sh and ./scripts/test_unit.sh before completing work."
    system_prompt+="\\n\\nRead .agent/skills/ for detailed guidance on code principles, testing, and architecture."

    cat > "$OPENCODE_JSON" << JSONEOF
{
  "\$schema": "https://opencode.ai/schema.json",
  "agents": {
    "coder": {
      "model": "sonnet",
      "systemPrompt": "$(json_escape "$system_prompt")"
    },
    "task": {
      "model": "sonnet",
      "systemPrompt": "You are a task planning agent for QuickScale. Break down tasks from docs/technical/roadmap.md into actionable steps."
    }
  },
  "lsp": {
    "python": {
      "command": "pyright-langserver",
      "args": ["--stdio"]
    }
  }
}
JSONEOF
}

# ─── Custom Commands (from .agent/workflows/) ──────────────────────────────────

generate_commands() {
    for wf_file in "$AGENT_DIR"/workflows/*.md; do
        [[ -f "$wf_file" ]] || continue

        local wf_name description command_file
        wf_name=$(basename "$wf_file" .md)
        description=$(get_frontmatter "$wf_file" "description")
        command_file="$COMMANDS_DIR/${wf_name}.md"

        # Extract step summaries from workflow
        local steps_summary
        steps_summary=$(get_body "$wf_file" \
            | grep -E '^## (Step|Stage) ' \
            | sed 's/^## //' \
            | nl -ba -s '. ' \
            | sed 's/^[[:space:]]*//' || true)
        if [[ -z "$steps_summary" ]]; then
            steps_summary=$(get_body "$wf_file" \
                | grep -E '^## ' \
                | head -8 \
                | nl -ba -s '. ' \
                | sed 's/^[[:space:]]*//' || true)
        fi

        {
            echo "# ${description}"
            echo ""
            echo "Follow the ${wf_name} workflow for QuickScale development."
            echo ""
            if [[ -n "$steps_summary" ]]; then
                echo "## Steps"
                echo ""
                echo "$steps_summary"
                echo ""
            fi
            echo "Target: \$TASK_ID"
            echo ""
            echo "Read the full workflow at \`.agent/workflows/${wf_name}.md\` and follow it step by step."
            echo ""
            echo "## Validation"
            echo ""
            echo "Always run before completing:"
            echo "\`\`\`bash"
            echo "./scripts/lint.sh"
            echo "./scripts/test_unit.sh"
            echo "\`\`\`"
        } > "$command_file"
    done
}

# ─── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo "  📦 OpenCode adapter: generating configuration..."

    generate_opencode_json
    echo "     ✅ .opencode.json"

    generate_commands
    local cmd_count
    cmd_count=$(find "$COMMANDS_DIR" -name '*.md' -type f 2>/dev/null | wc -l)
    echo "     ✅ .opencode/commands/ (${cmd_count} commands)"
}

main "$@"
