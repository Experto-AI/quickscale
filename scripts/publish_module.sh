#!/usr/bin/env bash
# Publish module changes to split branch

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Function to show usage
show_usage() {
    echo "Usage: $0 <module_name>"
    echo ""
    echo "Publish module changes to its split branch."
    echo ""
    echo "Available modules:"
    for module in $(ls quickscale_modules/ 2>/dev/null | grep -v "^$"); do
        echo "  - $module"
    done
    echo ""
    echo "Examples:"
    echo "  $0 auth      # Publish auth module"
    echo "  $0 billing   # Publish billing module"
    echo "  $0 teams     # Publish teams module"
}

# Check if module name is provided
if [ $# -eq 0 ]; then
    print_error "Module name is required"
    echo ""
    show_usage
    exit 1
fi

MODULE_NAME="$1"
MODULE_PATH="quickscale_modules/${MODULE_NAME}"
SPLIT_BRANCH="splits/${MODULE_NAME}-module"

# Check if we're in the right directory (has quickscale_modules)
if [ ! -d "quickscale_modules" ]; then
    print_error "quickscale_modules directory not found. Are you in the QuickScale repository root?"
    exit 1
fi

# Check if module exists
if [ ! -d "$MODULE_PATH" ]; then
    print_error "Module '$MODULE_NAME' not found in quickscale_modules/"
    echo ""
    print_info "Available modules:"
    for module in $(ls quickscale_modules/ 2>/dev/null | grep -v "^$"); do
        echo "  - $module"
    done
    exit 1
fi

# Check if git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not a git repository"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    print_warning "You have uncommitted changes. It's recommended to commit them first."
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Aborted by user"
        exit 0
    fi
fi

print_info "Publishing module: $MODULE_NAME"
print_info "Module path: $MODULE_PATH"
print_info "Split branch: $SPLIT_BRANCH"
echo ""

# Perform git subtree split
print_info "Running git subtree split..."
if git subtree split --prefix="$MODULE_PATH" -b "$SPLIT_BRANCH" --rejoin; then
    print_success "Git subtree split completed"
else
    print_error "Git subtree split failed"
    exit 1
fi

# Push to origin
print_info "Pushing split branch to origin..."
if git push --force origin "$SPLIT_BRANCH"; then
    print_success "Split branch pushed to origin"
else
    print_error "Failed to push split branch to origin"
    exit 1
fi

echo ""
print_success "Module '$MODULE_NAME' published successfully!"
print_info "Split branch: $SPLIT_BRANCH"
print_info "Users can now embed this module with: quickscale embed --module $MODULE_NAME"
