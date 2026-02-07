#!/usr/bin/env bash

set -euo pipefail

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$LIB_DIR/../.." && pwd)"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# shellcheck disable=SC1091
source "$LIB_DIR/common.sh"

file="${1:-}"
if [[ -z "$file" || ! -f "$file" ]]; then
    echo "Usage: parse_frontmatter.sh <markdown-file>" >&2
    exit 1
fi

frontmatter="$(get_frontmatter_block "$file")"

# Parse top-level scalar keys and list keys used by the agent format.
name="$(get_frontmatter_scalar "$file" "name")"
version="$(get_frontmatter_scalar "$file" "version")"
description="$(get_frontmatter_scalar "$file" "description")"
mode="$(get_frontmatter_scalar "$file" "mode")"

skills_json=$(get_frontmatter_list "$file" "skills" | json_array_from_lines)
delegates_json=$(get_frontmatter_list "$file" "delegates_to" | json_array_from_lines)
workflows_json=$(get_frontmatter_list "$file" "workflows" | json_array_from_lines)
requires_json=$(get_frontmatter_list "$file" "requires" | json_array_from_lines)
provides_json=$(get_frontmatter_list "$file" "provides" | json_array_from_lines)

jq -n \
  --arg file "$(abs_to_rel "$file")" \
  --arg frontmatter "$frontmatter" \
  --arg name "$name" \
  --arg version "$version" \
  --arg description "$description" \
  --arg mode "$mode" \
  --argjson skills "$skills_json" \
  --argjson delegates_to "$delegates_json" \
  --argjson workflows "$workflows_json" \
  --argjson requires "$requires_json" \
  --argjson provides "$provides_json" \
  '{
    file: $file,
    raw_frontmatter: $frontmatter,
    name: (if $name == "" then null else $name end),
    version: (if $version == "" then null else $version end),
    description: (if $description == "" then null else $description end),
    mode: (if $mode == "" then null else $mode end),
    skills: $skills,
    delegates_to: $delegates_to,
    workflows: $workflows,
    requires: $requires,
    provides: $provides
  }'
