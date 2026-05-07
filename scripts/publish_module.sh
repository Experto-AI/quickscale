#!/usr/bin/env bash
# Publish module changes to split branches

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

list_modules() {
    find quickscale_modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | LC_ALL=C sort
}

show_usage() {
    echo "Usage:"
    echo "  $0 <module_name> [--clean]"
    echo "  $0 --status"
    echo "  $0 --publish-outdated [--clean]"
    echo ""
    echo "Publish module changes to split branches, inspect module publish status,"
    echo "or publish every module whose split branch is missing or outdated."
    echo ""
    echo "Options:"
    echo "  --status             Show split-branch status for every module"
    echo "  --publish-outdated   Publish only modules with missing or outdated split branches"
    echo "  --clean              Clear git subtree cache before splitting"
    echo ""
    echo "Available modules:"
    while IFS= read -r module; do
        echo "  - $module"
    done < <(list_modules 2>/dev/null || true)
    echo ""
    echo "Examples:"
    echo "  $0 auth"
    echo "  $0 billing --clean"
    echo "  $0 --status"
    echo "  $0 --publish-outdated"
}

ensure_repo_root() {
    if [ ! -d "quickscale_modules" ]; then
        print_error "quickscale_modules directory not found. Are you in the QuickScale repository root?"
        exit 1
    fi

    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not a git repository"
        exit 1
    fi
}

module_exists() {
    local module_name="$1"
    [ -d "quickscale_modules/${module_name}" ]
}

has_uncommitted_changes() {
    [ -n "$(git status --porcelain --untracked-files=normal)" ]
}

warn_uncommitted_changes() {
    if has_uncommitted_changes; then
        print_warning "You have uncommitted changes. Split status and published branches only include committed history."
    fi
}

confirm_uncommitted_changes() {
    if has_uncommitted_changes; then
        print_warning "You have uncommitted changes. Published split branches only include committed history."
        echo ""
        read -r -p "Continue anyway? (y/N): " reply
        if [[ ! "$reply" =~ ^[Yy]$ ]]; then
            print_info "Aborted by user"
            exit 0
        fi
    fi
}

maybe_clean_subtree_cache() {
    if [ "$CLEAN_CACHE" = true ]; then
        print_info "Cleaning git subtree cache..."
        rm -rf .git/subtree-cache
    fi
}

get_local_split_sha() {
    local module_path="$1"
    local split_sha=""

    if ! split_sha="$(git subtree split --prefix="$module_path" --ignore-joins 2>/dev/null | tail -n 1)"; then
        return 1
    fi

    if [ -z "$split_sha" ]; then
        return 1
    fi

    printf '%s\n' "$split_sha"
}

get_published_split_ref() {
    local split_branch="$1"
    local published_sha=""

    published_sha="$(git rev-parse --verify "$split_branch" 2>/dev/null || true)"
    if [ -n "$published_sha" ]; then
        printf '%s|local-branch\n' "$published_sha"
        return 0
    fi

    published_sha="$(git rev-parse --verify "origin/$split_branch" 2>/dev/null || true)"
    if [ -n "$published_sha" ]; then
        printf '%s|remote-tracking\n' "$published_sha"
        return 0
    fi

    printf '|none\n'
}

get_module_publish_state() {
    local module_name="$1"
    local module_path="quickscale_modules/${module_name}"
    local split_branch="splits/${module_name}-module"
    local local_split_sha=""
    local published_info=""
    local published_sha=""
    local published_source=""

    if ! local_split_sha="$(get_local_split_sha "$module_path")"; then
        print_error "Could not compute subtree split for module '$module_name'"
        exit 1
    fi

    published_info="$(get_published_split_ref "$split_branch")"
    IFS='|' read -r published_sha published_source <<< "$published_info"

    if [ -z "$published_sha" ]; then
        printf 'unpublished|%s||%s\n' "$local_split_sha" "$published_source"
        return 0
    fi

    if [ "$local_split_sha" = "$published_sha" ]; then
        printf 'up-to-date|%s|%s|%s\n' "$local_split_sha" "$published_sha" "$published_source"
        return 0
    fi

    printf 'outdated|%s|%s|%s\n' "$local_split_sha" "$published_sha" "$published_source"
}

publish_module() {
    local module_name="$1"
    local module_path="quickscale_modules/${module_name}"
    local split_branch="splits/${module_name}-module"
    local output=""

    print_info "Publishing module: $module_name"
    print_info "Module path: $module_path"
    print_info "Split branch: $split_branch"
    echo ""

    print_info "Running git subtree split..."
    if output="$(git subtree split --prefix="$module_path" -b "$split_branch" --rejoin --ignore-joins 2>&1)"; then
        echo "$output"
        print_success "Git subtree split completed"
    else
        echo "$output"
        if [[ "$output" == *"cache for"* && "$output" == *"already exists"* ]]; then
            print_error "Git subtree split failed due to cache error."
            print_info "Try running with --clean to fix this:"
            print_info "  $0 $module_name --clean"
        else
            print_error "Git subtree split failed"
        fi
        exit 1
    fi

    print_info "Pushing split branch to origin..."
    if git push --force origin "$split_branch"; then
        print_success "Split branch pushed to origin"
    else
        print_error "Failed to push split branch to origin"
        exit 1
    fi

    echo ""
    print_success "Module '$module_name' published successfully!"
    print_info "Split branch: $split_branch"
    print_info "Users can now embed this module with: quickscale embed --module $module_name"
}

show_status() {
    local module_name=""
    local state=""
    local local_sha=""
    local published_sha=""
    local published_source=""
    local -a outdated_modules=()
    local -a unpublished_modules=()

    warn_uncommitted_changes
    print_info "Inspecting module publish status..."
    echo ""

    while IFS= read -r module_name; do
        IFS='|' read -r state local_sha published_sha published_source <<< "$(get_module_publish_state "$module_name")"
        case "$state" in
            up-to-date)
                printf '  %-16s %s\n' "$module_name" "up to date (${published_source})"
                ;;
            outdated)
                printf '  %-16s %s\n' "$module_name" "outdated (${published_source})"
                outdated_modules+=("$module_name")
                ;;
            unpublished)
                printf '  %-16s %s\n' "$module_name" "unpublished"
                unpublished_modules+=("$module_name")
                ;;
        esac
    done < <(list_modules)

    echo ""
    if [ ${#outdated_modules[@]} -eq 0 ] && [ ${#unpublished_modules[@]} -eq 0 ]; then
        print_success "All module split branches are up to date."
        return 0
    fi

    if [ ${#outdated_modules[@]} -gt 0 ]; then
        print_warning "Outdated modules: ${outdated_modules[*]}"
    fi

    if [ ${#unpublished_modules[@]} -gt 0 ]; then
        print_warning "Unpublished modules: ${unpublished_modules[*]}"
    fi
}

publish_outdated_modules() {
    local module_name=""
    local state=""
    local local_sha=""
    local published_sha=""
    local published_source=""
    local -a publish_queue=()

    confirm_uncommitted_changes
    maybe_clean_subtree_cache

    while IFS= read -r module_name; do
        IFS='|' read -r state local_sha published_sha published_source <<< "$(get_module_publish_state "$module_name")"
        case "$state" in
            outdated|unpublished)
                publish_queue+=("$module_name")
                ;;
        esac
    done < <(list_modules)

    if [ ${#publish_queue[@]} -eq 0 ]; then
        print_success "All module split branches are already up to date."
        return 0
    fi

    print_info "Publishing outdated modules: ${publish_queue[*]}"
    echo ""

    for module_name in "${publish_queue[@]}"; do
        publish_module "$module_name"
        echo ""
    done
}

ACTION="publish-single"
MODULE_NAME=""
CLEAN_CACHE=false

if [ $# -eq 0 ]; then
    print_error "A module name or mode flag is required"
    echo ""
    show_usage
    exit 1
fi

case "${1:-}" in
    --status)
        ACTION="status"
        shift
        ;;
    --publish-outdated)
        ACTION="publish-outdated"
        shift
        ;;
    --help|-h)
        show_usage
        exit 0
        ;;
    --*)
        print_error "Unknown option: $1"
        echo ""
        show_usage
        exit 1
        ;;
    *)
        MODULE_NAME="$1"
        shift
        ;;
esac

for arg in "$@"; do
    case "$arg" in
        --clean)
            CLEAN_CACHE=true
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $arg"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

if [ "$ACTION" = "status" ] && [ "$CLEAN_CACHE" = true ]; then
    print_error "--clean is only supported with publish actions"
    exit 1
fi

ensure_repo_root

case "$ACTION" in
    status)
        show_status
        ;;
    publish-outdated)
        publish_outdated_modules
        ;;
    publish-single)
        if [ -z "$MODULE_NAME" ]; then
            print_error "Module name is required"
            echo ""
            show_usage
            exit 1
        fi

        if ! module_exists "$MODULE_NAME"; then
            print_error "Module '$MODULE_NAME' not found in quickscale_modules/"
            echo ""
            print_info "Available modules:"
            while IFS= read -r module_name; do
                echo "  - $module_name"
            done < <(list_modules)
            exit 1
        fi

        confirm_uncommitted_changes
        maybe_clean_subtree_cache
        publish_module "$MODULE_NAME"
        ;;
esac
