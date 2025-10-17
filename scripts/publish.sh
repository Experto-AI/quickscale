#!/usr/bin/env bash
set -euo pipefail

# QuickScale Publishing Script for PyPI
# Usage:
#   scripts/publish.sh test       # Publish to TestPyPI only
#   scripts/publish.sh prod       # Publish to production PyPI only
#   scripts/publish.sh full       # Publish to TestPyPI, verify, then PyPI
#   scripts/publish.sh build      # Build packages only (no publish)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"
VERSION_TOOL="$ROOT/scripts/version_tool.sh"

# Package directories in publish order
PACKAGES=(
    "quickscale_core"
    "quickscale_cli"
    "quickscale"
)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

read_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        cat "$VERSION_FILE" | tr -d '\r' | sed -e 's/^\s*//' -e 's/\s*$//'
    else
        log_error "VERSION file not found at $VERSION_FILE"
        exit 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check poetry
    if ! command -v poetry &> /dev/null; then
        log_error "Poetry is not installed. Please install it first."
        exit 1
    fi
    log_success "Poetry found: $(poetry --version)"

    # Check if version_tool.sh exists
    if [[ ! -f "$VERSION_TOOL" ]]; then
        log_error "version_tool.sh not found at $VERSION_TOOL"
        exit 1
    fi

    # Check git status
    if [[ -n $(git status --porcelain) ]]; then
        log_warning "Working directory has uncommitted changes"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Aborted by user"
            exit 1
        fi
    else
        log_success "Git working tree is clean"
    fi
}

check_pypi_config() {
    local target="$1"  # "testpypi" or "pypi"

    log_info "Checking PyPI configuration for $target..."

    # Check if auth.toml exists
    local auth_file="${HOME}/.config/pypoetry/auth.toml"

    if [[ "$target" == "testpypi" ]]; then
        # Check if testpypi repository is configured
        local repo_url
        repo_url=$(poetry config repositories.testpypi 2>/dev/null || echo "")
        if [[ -z "$repo_url" ]]; then
            log_error "TestPyPI repository not configured."
            echo ""
            echo "Please run:"
            echo "  poetry config repositories.testpypi https://test.pypi.org/legacy/"
            echo "  poetry config pypi-token.testpypi <your-testpypi-token>"
            echo ""
            echo "Get your TestPyPI token at: https://test.pypi.org/manage/account/token/"
            exit 1
        fi

        # Check if testpypi token exists in auth.toml
        if [[ ! -f "$auth_file" ]] || ! grep -q "testpypi" "$auth_file" 2>/dev/null; then
            log_error "TestPyPI token not configured."
            echo ""
            echo "Please run:"
            echo "  poetry config pypi-token.testpypi <your-testpypi-token>"
            echo ""
            echo "Get your TestPyPI token at: https://test.pypi.org/manage/account/token/"
            exit 1
        fi

        log_success "TestPyPI is configured"
    else
        # Check if pypi token exists in auth.toml
        if [[ ! -f "$auth_file" ]] || ! grep -q 'pypi = ' "$auth_file" 2>/dev/null; then
            log_error "PyPI token not configured."
            echo ""
            echo "Please run:"
            echo "  poetry config pypi-token.pypi <your-pypi-token>"
            echo ""
            echo "Get your PyPI token at: https://pypi.org/manage/account/token/"
            echo ""
            echo "Example: poetry config pypi-token.pypi pypi-AgEIcH..."
            exit 1
        fi

        log_success "PyPI is configured"
    fi
}

check_version_consistency() {
    log_info "Checking version consistency..."
    if "$VERSION_TOOL" check; then
        log_success "All versions are consistent"
    else
        log_error "Version mismatch detected. Run 'scripts/version_tool.sh sync --apply' to fix."
        exit 1
    fi
}

run_tests() {
    log_info "Running tests for all packages..."

    local failed=0

    # Test quickscale_core
    log_info "Testing quickscale_core..."
    cd "$ROOT/quickscale_core"
    if poetry run pytest; then
        log_success "quickscale_core tests passed"
    else
        log_error "quickscale_core tests failed"
        failed=1
    fi

    # Test quickscale_cli
    log_info "Testing quickscale_cli..."
    cd "$ROOT/quickscale_cli"
    if poetry run pytest; then
        log_success "quickscale_cli tests passed"
    else
        log_error "quickscale_cli tests failed"
        failed=1
    fi

    cd "$ROOT"

    if [[ $failed -eq 1 ]]; then
        log_error "Some tests failed. Please fix them before publishing."
        exit 1
    fi

    log_success "All tests passed"
}

backup_pyproject() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    local backup="$pkg_dir/pyproject.toml.backup"

    if [[ -f "$pyproject" ]]; then
        cp "$pyproject" "$backup"
        log_info "Backed up $pyproject"
    else
        log_error "pyproject.toml not found in $pkg_dir"
        exit 1
    fi
}

restore_pyproject() {
    local pkg_dir="$1"
    local pyproject="$pkg_dir/pyproject.toml"
    local backup="$pkg_dir/pyproject.toml.backup"

    if [[ -f "$backup" ]]; then
        mv "$backup" "$pyproject"
        log_info "Restored $pyproject"
    fi
}

replace_path_deps() {
    local pkg_name="$1"
    local version="$2"
    local pkg_dir="$ROOT/$pkg_name"
    local pyproject="$pkg_dir/pyproject.toml"

    log_info "Replacing path dependencies in $pkg_name with version constraints..."

    case "$pkg_name" in
        "quickscale_cli")
            # Replace: quickscale-core = {path = "../quickscale_core", develop = true}
            # With:    quickscale-core = "^VERSION"
            sed -i "s|quickscale-core = {path = \"../quickscale_core\", develop = true}|quickscale-core = \"^${version}\"|" "$pyproject"
            log_success "Replaced quickscale-core path dependency"
            ;;
        "quickscale")
            # Replace both dependencies
            sed -i "s|quickscale-core = {path = \"../quickscale_core\", develop = true}|quickscale-core = \"^${version}\"|" "$pyproject"
            sed -i "s|quickscale-cli = {path = \"../quickscale_cli\", develop = true}|quickscale-cli = \"^${version}\"|" "$pyproject"
            log_success "Replaced quickscale-core and quickscale-cli path dependencies"
            ;;
        "quickscale_core")
            # No dependencies to replace
            log_info "No path dependencies to replace in quickscale_core"
            ;;
    esac
}

clean_dist() {
    local pkg_dir="$1"
    local dist_dir="$pkg_dir/dist"

    if [[ -d "$dist_dir" ]]; then
        log_info "Cleaning $dist_dir..."
        rm -rf "$dist_dir"/*
        log_success "Cleaned $dist_dir"
    else
        mkdir -p "$dist_dir"
        log_info "Created $dist_dir"
    fi
}

prepare_for_publish() {
    local version
    version=$(read_version)

    log_info "Preparing pyproject.toml files for publishing..."

    for pkg in "${PACKAGES[@]}"; do
        local pkg_dir="$ROOT/$pkg"
        copy_readme "$pkg_dir"
        backup_pyproject "$pkg_dir"
        replace_path_deps "$pkg" "$version"
    done

    log_success "All pyproject.toml files prepared for publishing"
}

restore_all_pyprojects() {
    log_info "Restoring original pyproject.toml files..."

    for pkg in "${PACKAGES[@]}"; do
        local pkg_dir="$ROOT/$pkg"
        restore_pyproject "$pkg_dir"
        remove_readme "$pkg_dir"
    done

    log_success "All pyproject.toml files restored"
}

copy_readme() {
    local pkg_dir="$1"
    local readme_src="$ROOT/README.md"
    local readme_dst="$pkg_dir/README.md"

    if [[ -f "$readme_src" ]] && [[ ! -f "$readme_dst" ]]; then
        cp "$readme_src" "$readme_dst"
        log_info "Copied README.md to $pkg_dir"
    fi
}

remove_readme() {
    local pkg_dir="$1"
    local readme="$pkg_dir/README.md"

    if [[ -f "$readme" ]]; then
        rm "$readme"
        log_info "Removed temporary README.md from $pkg_dir"
    fi
}

build_package() {
    local pkg_name="$1"
    local version="$2"
    local pkg_dir="$ROOT/$pkg_name"

    log_info "Building $pkg_name..."

    # Copy README.md for Poetry build
    copy_readme "$pkg_dir"

    # Backup original pyproject.toml
    backup_pyproject "$pkg_dir"

    # Replace path dependencies with version dependencies
    replace_path_deps "$pkg_name" "$version"

    # Clean dist directory
    clean_dist "$pkg_dir"

    # Build with poetry
    cd "$pkg_dir"
    if poetry build; then
        log_success "Built $pkg_name"
    else
        log_error "Failed to build $pkg_name"
        restore_pyproject "$pkg_dir"
        remove_readme "$pkg_dir"
        exit 1
    fi

    # Restore original pyproject.toml
    restore_pyproject "$pkg_dir"

    # Remove temporary README.md
    remove_readme "$pkg_dir"

    cd "$ROOT"
}

publish_package() {
    local pkg_name="$1"
    local repository="$2"  # "testpypi" or "pypi"
    local pkg_dir="$ROOT/$pkg_name"

    log_info "Publishing $pkg_name to $repository..."

    cd "$pkg_dir"

    # Use a temporary file to capture output while showing it in real-time
    local temp_output
    temp_output=$(mktemp)

    local exit_code

    # Temporarily disable exit-on-error to handle expected failures
    set +e
    if [[ "$repository" == "testpypi" ]]; then
        poetry publish --repository testpypi 2>&1 | tee "$temp_output"
        exit_code=${PIPESTATUS[0]}
    else
        poetry publish 2>&1 | tee "$temp_output"
        exit_code=${PIPESTATUS[0]}
    fi
    set -e

    local output
    output=$(cat "$temp_output")
    rm -f "$temp_output"

    echo ""  # Add newline for better formatting

    # Check if publish succeeded
    if [[ $exit_code -eq 0 ]]; then
        log_success "Published $pkg_name to $repository"
        cd "$ROOT"
        return 0
    fi

    # Check if the error is because the file already exists (version already published)
    if echo "$output" | grep -q "File already exists"; then
        log_warning "$pkg_name version already exists on $repository, skipping..."
        cd "$ROOT"
        return 0
    fi

    # Check if the error is because of invalid dependency format
    if echo "$output" | grep -q "Can't have direct dependency"; then
        log_error "Failed to publish $pkg_name: invalid dependency format"
        cd "$ROOT"
        exit 1
    fi

    # Any other error - fail
    log_error "Failed to publish $pkg_name to $repository"
    cd "$ROOT"
    exit 1
}

build_all_packages() {
    local version
    version=$(read_version)

    log_info "Building all packages (version $version)..."

    for pkg in "${PACKAGES[@]}"; do
        build_package "$pkg" "$version"
    done

    log_success "All packages built successfully"
}

publish_to_testpypi() {
    prepare_for_publish

    log_info "Publishing to TestPyPI..."

    local failed=0
    for pkg in "${PACKAGES[@]}"; do
        if ! publish_package "$pkg" "testpypi"; then
            failed=1
            break
        fi
    done

    restore_all_pyprojects

    if [[ $failed -eq 1 ]]; then
        exit 1
    fi

    log_success "All packages published to TestPyPI"

    local version
    version=$(read_version)

    echo ""
    log_info "Verify the packages on TestPyPI:"
    echo "  - https://test.pypi.org/project/quickscale-core/$version/"
    echo "  - https://test.pypi.org/project/quickscale-cli/$version/"
    echo "  - https://test.pypi.org/project/quickscale/$version/"
    echo ""
    log_info "You can test installation with:"
    echo "  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ quickscale==$version"
    echo ""
}

publish_to_pypi() {
    log_warning "You are about to publish to production PyPI. This action cannot be undone."
    read -p "Are you sure you want to continue? (yes/N): " -r
    echo
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log_error "Aborted by user"
        exit 1
    fi

    prepare_for_publish

    log_info "Publishing to PyPI..."

    local failed=0
    for pkg in "${PACKAGES[@]}"; do
        if ! publish_package "$pkg" "pypi"; then
            failed=1
            break
        fi
    done

    restore_all_pyprojects

    if [[ $failed -eq 1 ]]; then
        exit 1
    fi

    log_success "All packages published to PyPI"

    local version
    version=$(read_version)

    echo ""
    log_info "Packages are now live on PyPI:"
    echo "  - https://pypi.org/project/quickscale-core/$version/"
    echo "  - https://pypi.org/project/quickscale-cli/$version/"
    echo "  - https://pypi.org/project/quickscale/$version/"
    echo ""
    log_info "Users can now install with:"
    echo "  pip install quickscale==$version"
    echo ""
}

cmd_build() {
    check_prerequisites
    check_version_consistency
    run_tests
    build_all_packages

    log_success "Build complete! Packages are in dist/ directories."
    log_info "To publish, run:"
    echo "  ./scripts/publish.sh test   # Publish to TestPyPI"
    echo "  ./scripts/publish.sh prod   # Publish to PyPI"
    echo "  ./scripts/publish.sh full   # Publish to both"
}

cmd_test() {
    check_prerequisites
    check_pypi_config "testpypi"
    check_version_consistency
    run_tests
    build_all_packages
    publish_to_testpypi
}

cmd_prod() {
    check_prerequisites
    check_pypi_config "pypi"
    check_version_consistency

    # Check if packages are already built
    local all_built=true
    for pkg in "${PACKAGES[@]}"; do
        if [[ ! -d "$ROOT/$pkg/dist" ]] || [[ -z "$(ls -A "$ROOT/$pkg/dist" 2>/dev/null)" ]]; then
            all_built=false
            break
        fi
    done

    if [[ "$all_built" == false ]]; then
        log_warning "Packages not built yet. Building now..."
        run_tests
        build_all_packages
    else
        log_info "Using existing builds in dist/ directories"
    fi

    publish_to_pypi
}

cmd_full() {
    check_prerequisites
    check_pypi_config "testpypi"
    check_pypi_config "pypi"
    check_version_consistency
    run_tests
    build_all_packages
    publish_to_testpypi

    echo ""
    log_info "TestPyPI publish complete."
    read -p "After verifying on TestPyPI, press Enter to publish to production PyPI (or Ctrl+C to abort)..."

    publish_to_pypi
}

usage() {
    cat <<EOF
QuickScale Publishing Script for PyPI

Usage: $0 <command>

Commands:
  build    Build all packages (no publish)
  test     Build and publish to TestPyPI only
  prod     Build and publish to production PyPI
  full     Build, publish to TestPyPI, verify, then publish to PyPI

Prerequisites:
  - Poetry installed and configured
  - PyPI credentials configured:
      poetry config pypi-token.pypi <your-token>
      poetry config repositories.testpypi https://test.pypi.org/legacy/
      poetry config pypi-token.testpypi <your-testpypi-token>

Workflow:
  1. The script checks version consistency
  2. Runs tests for all packages
  3. Builds packages in order: quickscale-core → quickscale-cli → quickscale
  4. Automatically handles path dependencies (backs up, replaces, restores)
  5. Publishes to TestPyPI and/or PyPI

Examples:
  # Safe workflow: test on TestPyPI first
  $0 test
  # After verifying, publish to production
  $0 prod

  # Or do everything in one go (with verification step)
  $0 full

  # Just build without publishing
  $0 build

Notes:
  - Always test on TestPyPI before publishing to production
  - The script automatically handles path→version dependency conversion
  - All pyproject.toml files are restored after build
  - Git working tree should be clean (warnings if not)

EOF
}

main() {
    if [[ $# -lt 1 ]]; then
        usage
        exit 2
    fi

    cmd="$1"
    shift

    case "$cmd" in
        build)
            cmd_build ;;
        test)
            cmd_test ;;
        prod)
            cmd_prod ;;
        full)
            cmd_full ;;
        -h|--help|help)
            usage ;;
        *)
            log_error "Unknown command: $cmd"
            usage
            exit 2 ;;
    esac
}

main "$@"
