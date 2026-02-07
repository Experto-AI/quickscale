#!/usr/bin/env bash

set -euo pipefail

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$LIB_DIR/../.." && pwd)"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# shellcheck disable=SC1091
source "$LIB_DIR/common.sh"

ensure_build_dirs

ir_file="${1:-$IR_FILE_DEFAULT}"
strict_mode="$(strict_mode_enabled)"

tmp_agents="$(mktemp)"
tmp_subagents="$(mktemp)"
tmp_skills="$(mktemp)"
tmp_workflows="$(mktemp)"
tmp_contexts="$(mktemp)"
trap 'rm -f "$tmp_agents" "$tmp_subagents" "$tmp_skills" "$tmp_workflows" "$tmp_contexts"' EXIT

entity_from_file() {
    local kind="$1" file="$2"

    local rel_path name description version mode
    local frontmatter body_hash
    local skills delegates workflows parents requires provides
    local dir_skills dir_agents dir_workflows
    local inputs_yaml outputs_yaml success_yaml

    rel_path="$(abs_to_rel "$file")"
    name="$(get_frontmatter_scalar "$file" "name")"
    if [[ -z "$name" ]]; then
        name="$(basename "$file" .md)"
    fi
    description="$(get_frontmatter_scalar "$file" "description")"
    version="$(get_frontmatter_scalar "$file" "version")"
    mode="$(get_frontmatter_scalar "$file" "mode")"

    skills=$(get_frontmatter_list "$file" "skills" | json_array_from_lines)
    delegates=$(get_frontmatter_list "$file" "delegates_to" | json_array_from_lines)
    workflows=$(get_frontmatter_list "$file" "workflows" | json_array_from_lines)
    parents=$(get_frontmatter_list "$file" "parent_agents" | json_array_from_lines)
    requires=$(get_frontmatter_list "$file" "requires" | json_array_from_lines)
    provides=$(get_frontmatter_list "$file" "provides" | json_array_from_lines)

    dir_skills=$(get_directives "$file" "skill" | json_array_from_lines)
    dir_agents=$(get_directives "$file" "agent" | json_array_from_lines)
    dir_workflows=$(get_directives "$file" "workflow" | json_array_from_lines)

    inputs_yaml="$(get_frontmatter_section "$file" "inputs")"
    outputs_yaml="$(get_frontmatter_section "$file" "outputs")"
    success_yaml="$(get_frontmatter_section "$file" "success_when")"

    frontmatter="$(get_frontmatter_block "$file")"
    body_hash="$(sha256sum "$file" | awk '{print $1}')"

    jq -n \
        --arg name "$name" \
        --arg kind "$kind" \
        --arg path "$rel_path" \
        --arg description "$description" \
        --arg version "$version" \
        --arg mode "$mode" \
        --arg frontmatter "$frontmatter" \
        --arg body_hash "$body_hash" \
        --arg inputs_yaml "$inputs_yaml" \
        --arg outputs_yaml "$outputs_yaml" \
        --arg success_yaml "$success_yaml" \
        --argjson skills "$skills" \
        --argjson delegates "$delegates" \
        --argjson workflows "$workflows" \
        --argjson parents "$parents" \
        --argjson requires "$requires" \
        --argjson provides "$provides" \
        --argjson dir_skills "$dir_skills" \
        --argjson dir_agents "$dir_agents" \
        --argjson dir_workflows "$dir_workflows" \
        '{
            name: $name,
            kind: $kind,
            path: $path,
            description: $description,
            version: (if $version == "" then null else $version end),
            mode: (if $mode == "" then null else $mode end),
            skills: $skills,
            delegates_to: $delegates,
            workflows: $workflows,
            parent_agents: $parents,
            requires: $requires,
            provides: $provides,
            directives: {
                skills: $dir_skills,
                agents: $dir_agents,
                workflows: $dir_workflows
            },
            contract: {
                inputs_yaml: $inputs_yaml,
                outputs_yaml: $outputs_yaml,
                success_when_yaml: $success_yaml
            },
            frontmatter: $frontmatter,
            body_hash: $body_hash
        }'
}

for file in "$AGENT_DIR"/agents/*.md; do
    [[ -f "$file" ]] || continue
    entity_from_file "agent" "$file" >> "$tmp_agents"
done

for file in "$AGENT_DIR"/subagents/*.md; do
    [[ -f "$file" ]] || continue
    entity_from_file "subagent" "$file" >> "$tmp_subagents"
done

for file in "$AGENT_DIR"/skills/*/SKILL.md; do
    [[ -f "$file" ]] || continue
    entity_from_file "skill" "$file" >> "$tmp_skills"
done

for file in "$AGENT_DIR"/workflows/*.md; do
    [[ -f "$file" ]] || continue
    entity_from_file "workflow" "$file" >> "$tmp_workflows"
done

for file in "$AGENT_DIR"/contexts/*.md; do
    [[ -f "$file" ]] || continue
    entity_from_file "context" "$file" >> "$tmp_contexts"
done

agents_json="$(jq -s '.' "$tmp_agents")"
subagents_json="$(jq -s '.' "$tmp_subagents")"
skills_json="$(jq -s '.' "$tmp_skills")"
workflows_json="$(jq -s '.' "$tmp_workflows")"
contexts_json="$(jq -s '.' "$tmp_contexts")"

tmp_ir="$(mktemp)"
trap 'rm -f "$tmp_agents" "$tmp_subagents" "$tmp_skills" "$tmp_workflows" "$tmp_contexts" "$tmp_ir"' EXIT

jq -n \
    --arg schema_version "$(get_frontmatter_scalar "$AGENT_DIR/config.yaml" "schema_version")" \
    --arg generated_at "$(date -Iseconds)" \
    --arg output_directory "$(config_output_directory)" \
    --arg lint_command "$(resolve_lint_command)" \
    --arg test_command "$(resolve_test_command)" \
    --arg strict_mode "$strict_mode" \
    --argjson claude_code "$(platform_enabled "claude_code" | jq -R 'ascii_downcase == "true"')" \
    --argjson gemini_cli "$(platform_enabled "gemini_cli" | jq -R 'ascii_downcase == "true"')" \
    --argjson gemini_antigravity "$(platform_enabled "gemini_antigravity" | jq -R 'ascii_downcase == "true"')" \
    --argjson github_copilot "$(platform_enabled "github_copilot" | jq -R 'ascii_downcase == "true"')" \
    --argjson copilot_cli "$(platform_enabled "copilot_cli" | jq -R 'ascii_downcase == "true"')" \
    --argjson codex_cli "$(platform_enabled "codex_cli" | jq -R 'ascii_downcase == "true"')" \
    --argjson opencode "$(platform_enabled "opencode" | jq -R 'ascii_downcase == "true"')" \
    --argjson agents "$agents_json" \
    --argjson subagents "$subagents_json" \
    --argjson skills "$skills_json" \
    --argjson workflows "$workflows_json" \
    --argjson contexts "$contexts_json" \
    '{
        schema_version: (if $schema_version == "" then "1.0" else $schema_version end),
        generated_at: $generated_at,
        config: {
            output_directory: $output_directory,
            lint_command: $lint_command,
            test_command: $test_command,
            strict_mode: ($strict_mode == "true"),
            platforms: {
                claude_code: $claude_code,
                gemini_cli: $gemini_cli,
                gemini_antigravity: $gemini_antigravity,
                github_copilot: $github_copilot,
                copilot_cli: $copilot_cli,
                codex_cli: $codex_cli,
                opencode: $opencode
            }
        },
        agents: $agents,
        subagents: $subagents,
        skills: $skills,
        workflows: $workflows,
        contexts: $contexts,
        diagnostics: {
            errors: [],
            warnings: []
        }
    }' > "$tmp_ir"

errors_file="$(mktemp)"
trap 'rm -f "$tmp_agents" "$tmp_subagents" "$tmp_skills" "$tmp_workflows" "$tmp_contexts" "$tmp_ir" "$errors_file"' EXIT

jq -r '
    . as $root
    | ($root.agents + $root.subagents)[] as $entity
    | (($entity.skills + $entity.directives.skills)[]?) as $skill
    | select(($root.skills | map(.name) | index($skill)) == null)
    | "missing-skill\t\($entity.kind)\t\($entity.name)\t\($skill)"
' "$tmp_ir" >> "$errors_file"

jq -r '
    . as $root
    | ($root.agents + $root.subagents)[] as $entity
    | (($entity.delegates_to + $entity.directives.agents)[]?) as $agent
    | select((($root.agents + $root.subagents) | map(.name) | index($agent)) == null)
    | "missing-agent\t\($entity.kind)\t\($entity.name)\t\($agent)"
' "$tmp_ir" >> "$errors_file"

jq -r '
    . as $root
    | ($root.agents + $root.subagents)[] as $entity
    | (($entity.workflows + $entity.directives.workflows)[]?) as $workflow
    | select(($root.workflows | map(.name) | index($workflow)) == null)
    | "missing-workflow\t\($entity.kind)\t\($entity.name)\t\($workflow)"
' "$tmp_ir" >> "$errors_file"

jq -r '
    . as $root
    | $root.subagents[] as $entity
    | ($entity.parent_agents[]?) as $parent
    | select(($root.agents | map(.name) | index($parent)) == null)
    | "missing-parent-agent\t\($entity.kind)\t\($entity.name)\t\($parent)"
' "$tmp_ir" >> "$errors_file"

jq -r '
    . as $root
    | $root.skills[] as $skill
    | ($skill.requires[]?) as $required
    | select(($root.skills | map(.name) | index($required)) == null)
    | "missing-required-skill\tskill\t\($skill.name)\t\($required)"
' "$tmp_ir" >> "$errors_file"

# Cycle detection for skill requires graph.
declare -A skill_requires
while IFS=$'\t' read -r skill_name reqs; do
    skill_requires["$skill_name"]="$reqs"
done < <(jq -r '.skills[] | [.name, (.requires | join(","))] | @tsv' "$tmp_ir")

declare -A visit_state

dfs_skill_cycle() {
    local node="$1" path="$2"
    local state="${visit_state[$node]:-0}"

    if [[ "$state" == "1" ]]; then
        printf 'cycle-skill\tskill\t%s\t%s -> %s\n' "$node" "$path" "$node" >> "$errors_file"
        return 0
    fi
    if [[ "$state" == "2" ]]; then
        return 0
    fi

    visit_state["$node"]=1

    local req_list req
    req_list="${skill_requires[$node]:-}"
    IFS=',' read -r -a reqs <<< "$req_list"
    for req in "${reqs[@]}"; do
        [[ -n "$req" ]] || continue
        if [[ -v "skill_requires[$req]" ]]; then
            dfs_skill_cycle "$req" "${path}${path:+ -> }$node"
        fi
    done

    visit_state["$node"]=2
}

for skill_name in "${!skill_requires[@]}"; do
    dfs_skill_cycle "$skill_name" ""
done

mapfile -t diagnostics < <(awk 'NF' "$errors_file" | sort -u)

if [[ ${#diagnostics[@]} -gt 0 ]]; then
    local_diag_file="$(mktemp)"
    trap 'rm -f "$tmp_agents" "$tmp_subagents" "$tmp_skills" "$tmp_workflows" "$tmp_contexts" "$tmp_ir" "$errors_file" "$local_diag_file"' EXIT

    {
        for row in "${diagnostics[@]}"; do
            printf '%s\n' "$row"
        done
    } | jq -R -s 'split("\n") | map(select(length>0))' > "$local_diag_file"

    jq --argjson errs "$(cat "$local_diag_file")" '.diagnostics.errors = $errs' "$tmp_ir" > "$tmp_ir.with_errors"
    mv "$tmp_ir.with_errors" "$tmp_ir"

    if [[ "$strict_mode" == "true" ]]; then
        err "IR validation failed in strict mode:"
        for row in "${diagnostics[@]}"; do
            err "  $row"
        done
        exit 1
    fi
fi

mv "$tmp_ir" "$ir_file"
info "Built IR: $(abs_to_rel "$ir_file")"
