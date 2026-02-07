#!/usr/bin/env bash

# Shared rendering helpers for adapter outputs.

render_contract_block() {
    local file="$1"
    local mode inputs outputs success

    mode="$(get_frontmatter_scalar "$file" "mode")"
    inputs="$(get_frontmatter_section "$file" "inputs")"
    outputs="$(get_frontmatter_section "$file" "outputs")"
    success="$(get_frontmatter_section "$file" "success_when")"

    if [[ -z "$mode" && -z "$inputs" && -z "$outputs" && -z "$success" ]]; then
        return 0
    fi

    cat << 'HEADER'
## Contract Metadata

```yaml
HEADER

    if [[ -n "$mode" ]]; then
        printf 'mode: %s\n' "$mode"
    fi
    if [[ -n "$inputs" ]]; then
        printf '%s\n' "$inputs"
    fi
    if [[ -n "$outputs" ]]; then
        printf '%s\n' "$outputs"
    fi
    if [[ -n "$success" ]]; then
        printf '%s\n' "$success"
    fi

    cat << 'FOOTER'
```

FOOTER
}

render_validation_block() {
    local lint_cmd="$1"
    local test_cmd="$2"

    cat << BLOCK
## Validation

\`\`\`bash
${lint_cmd}
${test_cmd}
\`\`\`

BLOCK
}

render_contract_note_block() {
    local supported="$1"
    cat << BLOCK
## Contract Notes

Platform support for structured contract fields: ${supported}
When unsupported natively, this file preserves source metadata via the Contract Metadata section.

BLOCK
}

collect_step_headings() {
    local file="$1"
    local steps

    steps=$(get_body "$file" \
        | grep -E '^## (Step|Stage) ' \
        | sed 's/^## //' \
        | nl -ba -s '. ' \
        | sed 's/^[[:space:]]*//' || true)

    if [[ -z "$steps" ]]; then
        steps=$(get_body "$file" \
            | grep -E '^## ' \
            | head -8 \
            | sed 's/^## //' \
            | nl -ba -s '. ' \
            | sed 's/^[[:space:]]*//' || true)
    fi

    printf '%s\n' "$steps"
}
