#!/usr/bin/env bash
# Generate all enabled platform configurations from .agent/ source files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$AGENT_DIR")"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

check_deps() {
    local missing=()
    local cmd
    for cmd in bash cat sed grep awk jq; do
        if ! command -v "$cmd" > /dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        err "Missing dependencies: ${missing[*]}"
        exit 1
    fi
}

validate_ir() {
    local ir_file="$1"
    jq -e '.schema_version and .config and .agents and .workflows and .diagnostics' "$ir_file" > /dev/null
}

run_adapter() {
    local name="$1" key="$2" script="$3"
    local enabled support_mode experimental

    enabled="$(platform_enabled "$key")"
    support_mode="$(platform_support_mode "$key")"
    experimental="$(platform_experimental "$key")"
    if [[ "$enabled" != "true" ]]; then
        info "${name}: disabled in .agent/config.yaml"
        cleanup_manifest_platform "$key"
        return 0
    fi
    if [[ "$support_mode" == "disabled" ]]; then
        info "${name}: support_mode=disabled"
        cleanup_manifest_platform "$key"
        return 0
    fi

    if [[ ! -f "$SCRIPT_DIR/$script" ]]; then
        warn "${name}: adapter script '$script' not found"
        return 0
    fi

    if [[ "$experimental" == "true" ]]; then
        warn "${name}: experimental adapter enabled"
    fi
    info "${name}: generating (support_mode=${support_mode})"
    IR_FILE="$IR_FILE_DEFAULT" OUTPUT_ROOT="$(resolve_output_root)" bash "$SCRIPT_DIR/$script"
}

main() {
    check_deps
    ensure_build_dirs

    local output_root
    output_root="$(resolve_output_root)"
    mkdir -p "$output_root"

    echo "Agentic Flow — Platform Configuration Generator"
    echo "================================================"
    echo "Source: $AGENT_DIR"
    echo "Output root: $output_root"
    echo ""

    info "Building normalized IR"
    bash "$SCRIPT_DIR/build-ir.sh" "$IR_FILE_DEFAULT"
    validate_ir "$IR_FILE_DEFAULT"

    run_adapter "Claude Code" "claude_code" "claude-adapter.sh"
    run_adapter "Gemini CLI" "gemini_cli" "gemini-adapter.sh"
    run_adapter "GitHub Copilot (VS Code)" "github_copilot" "copilot-adapter.sh"
    run_adapter "Codex CLI" "codex_cli" "codex-adapter.sh"
    cleanup_manifest_platform "gemini_antigravity"
    cleanup_manifest_platform "copilot_cli"
    cleanup_manifest_platform "opencode"

    echo ""
    echo "================================================"
    echo "Generation complete"

    if compgen -G "$MANIFEST_DIR/*.txt" > /dev/null; then
        echo ""
        echo "Generated files by platform:"
        local manifest platform count
        for manifest in "$MANIFEST_DIR"/*.txt; do
            platform="$(basename "$manifest" .txt)"
            count="$(awk 'NF' "$manifest" | wc -l | tr -d ' ')"
            printf '  - %s: %s files\n' "$platform" "$count"
        done
    fi

    echo ""
    echo "IR: $(abs_to_rel "$IR_FILE_DEFAULT")"
}

main "$@"
