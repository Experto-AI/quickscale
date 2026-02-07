#!/usr/bin/env bash

set -euo pipefail

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$LIB_DIR/../.." && pwd)"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# shellcheck disable=SC1091
source "$LIB_DIR/common.sh"

file="${1:-}"
if [[ -z "$file" || ! -f "$file" ]]; then
    echo "Usage: parse_directives.sh <markdown-file>" >&2
    exit 1
fi

skills_json=$(get_directives "$file" "skill" | json_array_from_lines)
agents_json=$(get_directives "$file" "agent" | json_array_from_lines)
workflows_json=$(get_directives "$file" "workflow" | json_array_from_lines)

jq -n \
  --arg file "$(abs_to_rel "$file")" \
  --argjson skills "$skills_json" \
  --argjson agents "$agents_json" \
  --argjson workflows "$workflows_json" \
  '{
    file: $file,
    invoke_skill: $skills,
    invoke_agent: $agents,
    invoke_workflow: $workflows
  }'
