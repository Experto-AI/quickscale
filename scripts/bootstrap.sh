#!/usr/bin/env bash
# Bootstrap development environment with Poetry

set -e

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "❌ Do not run bootstrap with sudo/root."
    echo "Running as root creates root-owned cache/.venv files that break local Poetry workflows."
    exit 1
fi

echo "🚀 Bootstrapping QuickScale development environment..."
echo ""

# Check Python version
echo "📋 Checking Python version..."
required_version="3.14"

PYTHON_CMD=""
if command -v python3.14 &> /dev/null; then
    PYTHON_CMD="python3.14"
elif command -v python3 &> /dev/null; then
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 14) else 1)"; then
        PYTHON_CMD="python3"
    fi
fi

if [[ -z "$PYTHON_CMD" ]]; then
    detected_version="unknown"
    if command -v python3 &> /dev/null; then
        detected_version="$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)"
    fi

    echo "❌ Python $required_version or higher is required (found $detected_version)"
    echo "Install python3.14 and retry (or ensure python3 points to 3.14+)"
    exit 1
fi

echo "✓ Python version: $($PYTHON_CMD --version)"
echo ""

if [[ -d ".venv" ]]; then
    venv_uid="$(stat -c '%u' .venv 2>/dev/null || echo '')"
    current_uid="$(id -u)"

    if [[ -n "$venv_uid" && "$venv_uid" != "$current_uid" ]]; then
        backup_path=".venv.root-owned.backup.$(date +%Y%m%d-%H%M%S)"
        echo "⚠️  Found .venv not owned by current user (uid=$venv_uid, current=$current_uid)."
        echo "   This usually happens after running Poetry with sudo."
        echo "   Moving broken .venv to $backup_path so Poetry can recreate it..."

        if mv .venv "$backup_path"; then
            echo "✓ Moved old .venv to $backup_path"
        else
            echo "❌ Could not move .venv automatically."
            echo "Run one of:"
            echo "  sudo chown -R \"$USER:$USER\" .venv"
            echo "  sudo rm -rf .venv"
            exit 1
        fi
        echo ""
    fi
fi

# Check if Poetry is installed
echo "📋 Checking Poetry installation..."
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed"
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | "$PYTHON_CMD" -
    echo ""
    echo "✓ Poetry installed"
    echo "⚠️  Please restart your shell or run: source $HOME/.local/bin/env"
    echo "⚠️  Then run this script again"
    exit 0
else
    echo "✓ Poetry version: $(poetry --version)"
fi
echo ""

# Configure Poetry to create virtual environments in project directory
echo "🔧 Configuring Poetry..."
poetry config virtualenvs.in-project true
echo "✓ Poetry configured to use .venv in project"
echo ""

echo "🔧 Ensuring root Poetry environment uses $PYTHON_CMD..."
poetry env use "$PYTHON_CMD" >/dev/null
ROOT_VENV_PATH="$(poetry env info -p 2>/dev/null || true)"

if [[ -z "$ROOT_VENV_PATH" ]]; then
    echo "❌ Could not resolve Poetry virtual environment path"
    exit 1
fi

export VIRTUAL_ENV="$ROOT_VENV_PATH"
export PATH="$ROOT_VENV_PATH/bin:$PATH"
export POETRY_ACTIVE=1

echo "✓ Using root virtual environment: $ROOT_VENV_PATH"
echo ""

# Install quickscale_core with dev dependencies
echo "📦 Installing quickscale_core..."
cd quickscale_core
poetry install
cd ..
echo ""

# Install quickscale_cli with dev dependencies
echo "📦 Installing quickscale_cli..."
cd quickscale_cli
poetry install
cd ..
echo ""

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x scripts/*.sh
echo ""

echo "✅ Bootstrap complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Activate Poetry shell:"
echo "     cd quickscale_core && poetry shell"
echo "     OR"
echo "     cd quickscale_cli && poetry shell"
echo ""
echo "  2. Run unit and integration tests: ./scripts/test_unit.sh"
echo "  3. Run linters: ./scripts/lint.sh"
echo "  4. Try the CLI:"
echo "     cd quickscale_cli && poetry run quickscale --help"
echo ""
echo "💡 Tip: Use 'poetry run <command>' to run commands in the Poetry environment"
echo "💡 Or use 'poetry shell' to activate the environment"
echo ""
echo "Happy coding! 🎉"
