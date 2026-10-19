#!/bin/bash

# compile_docs.sh
# Mirror each docs/contrib/*.md guide into .cursor/rules/*.mdc with Cursor frontmatter.
# docs/contrib/contributing.md is the hand-written guide map and is never generated.

set -euo pipefail

CONTRIB_DIR="docs/contrib"
CURSOR_RULES_DIR=".cursor/rules"

mkdir -p "$CURSOR_RULES_DIR"
rm -f "$CURSOR_RULES_DIR"/*

for file in $(ls -1 "$CONTRIB_DIR"/*.md | sort); do
    base_filename=$(basename "$file" .md)
    target_file="$CURSOR_RULES_DIR/${base_filename}.mdc"
    description=$(echo "$base_filename" | tr '_' ' ' | tr '[:upper:]' '[:lower:]')

    {
        echo "---"
        echo "description: $description"
        echo "globs: "
        echo "alwaysApply: false"
        echo "---"
        echo ""
        cat "$file"
    } > "$target_file"
done

echo "Cursor rules written to $CURSOR_RULES_DIR"
