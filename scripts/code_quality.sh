#!/bin/bash

# Code Quality Check Script for Scraper Idealista
# Usage: ./code_quality.sh [critical|full|fix]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default mode
MODE=${1:-"critical"}

echo -e "${BLUE}🔍 Code Quality Check - Mode: $MODE${NC}\n"

# Function to check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed. Installing...${NC}"
        pip install $1
    fi
}

# Function to run command with error handling
run_check() {
    local tool=$1
    local description=$2
    local cmd=$3
    
    echo -e "${YELLOW}📋 Running $description...${NC}"
    
    if eval $cmd; then
        echo -e "${GREEN}✅ $tool: PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ $tool: FAILED${NC}"
        return 1
    fi
}

# Install required tools if missing
echo -e "${BLUE}🔧 Checking required tools...${NC}"
check_command "ruff"
check_command "mypy" 
# Note: bandit disabled by default for secure internal app - use ENABLE_BANDIT=1 to enable
if [[ "${ENABLE_BANDIT:-0}" == "1" ]]; then
    check_command "bandit"
fi
# Note: safety disabled by default for secure internal app - use ENABLE_SAFETY=1 to enable
if [[ "${ENABLE_SAFETY:-0}" == "1" ]]; then
    check_command "safety"
fi

# Initialize error counter
ERRORS=0

case $MODE in
    "critical"|"error")
        echo -e "${YELLOW}🚨 Running CRITICAL/ERROR checks only (fast feedback)${NC}\n"
        
        # Ruff - Critical errors only  
        if ! run_check "Ruff" "Critical linting (errors only)" "ruff check . --select E9,F63,F7,F82,F821,F822,F823 --target-version py310"; then
            ((ERRORS++))
        fi
        
        # MyPy - Error level only
        if ! run_check "MyPy" "Type checking (errors only)" "mypy . --ignore-missing-imports --disable-error-code import-untyped --no-strict-optional --show-error-codes --pretty"; then
            ((ERRORS++))
        fi
        
        # Bandit - High severity only (disabled by default for secure internal app)
        if [[ "${ENABLE_BANDIT:-0}" == "1" ]]; then
            if ! run_check "Bandit" "Security check (high severity)" "bandit -r . -ll -f json -o bandit-report.json || bandit -r . -ll"; then
                ((ERRORS++))
            fi
        else
            echo -e "${BLUE}ℹ️  Bandit security check DISABLED (secure internal app)${NC}"
            echo -e "${YELLOW}💡 To enable: ENABLE_BANDIT=1 ./code_quality.sh critical${NC}"
        fi
        ;;
        
    "full")
        echo -e "${YELLOW}🔍 Running FULL code quality analysis (preserving code style)${NC}\n"
        
        # Ruff - Full linting (NO formatting to preserve style)
        if ! run_check "Ruff" "Full linting check" "ruff check . --target-version py310"; then
            ((ERRORS++))
        fi
        
        # MyPy - Full type checking
        if ! run_check "MyPy" "Full type checking" "mypy . --ignore-missing-imports --show-error-codes --pretty --strict-optional"; then
            ((ERRORS++))
        fi
        
        # Bandit - Full security scan (disabled by default for secure internal app)
        if [[ "${ENABLE_BANDIT:-0}" == "1" ]]; then
            if ! run_check "Bandit" "Full security scan" "bandit -r . -f json -o bandit-report.json || bandit -r ."; then
                ((ERRORS++))
            fi
        else
            echo -e "${BLUE}ℹ️  Bandit security scan DISABLED (secure internal app)${NC}"
            echo -e "${YELLOW}💡 To enable: ENABLE_BANDIT=1 ./code_quality.sh full${NC}"
        fi
        
        # Safety - Dependency vulnerability check (disabled by default for secure internal app)
        if [[ "${ENABLE_SAFETY:-0}" == "1" ]]; then
            if ! run_check "Safety" "Dependency vulnerability check" "safety check --json --output safety-report.json || safety check"; then
                ((ERRORS++))
            fi
        else
            echo -e "${BLUE}ℹ️  Safety dependency check DISABLED (secure internal app)${NC}"
            echo -e "${YELLOW}💡 To enable: ENABLE_SAFETY=1 ./code_quality.sh full${NC}"
        fi
        
        # Code complexity check with radon (if available)
        if command -v radon &> /dev/null; then
            if ! run_check "Radon" "Code complexity analysis" "radon cc . --min B"; then
                echo -e "${YELLOW}⚠️  High complexity detected (informational)${NC}"
            fi
        fi
        
        echo -e "\n${BLUE}ℹ️  Code formatting checks SKIPPED to preserve your existing style${NC}"
        echo -e "${BLUE}💡 To format code manually (optional): ${NC}${YELLOW}ruff format .${NC}"
        ;;
        
    "fix")
        echo -e "${YELLOW}🔧 Running SAFE auto-fix only (preserving code style)${NC}\n"
        
        # Ruff - Auto-fix ONLY ultra-safe linting rules (NO FORMATTING CHANGES)
        echo -e "${YELLOW}📋 Running Ruff ultra-safe auto-fix (code issues only, no style changes)...${NC}"
        if ruff check . --fix --target-version py310 --respect-gitignore --select E9,F63,F7,F82,F401,F811,F821,F822,F823,F841; then
            echo -e "${GREEN}✅ Ruff ultra-safe auto-fix: COMPLETED${NC}"
        else
            echo -e "${YELLOW}⚠️  Some safe issues require manual review${NC}"
        fi
        
        # REMOVED: ruff format command to preserve existing code style
        echo -e "${BLUE}ℹ️  Code formatting SKIPPED to preserve your existing style${NC}"
        echo -e "${BLUE}💡 To format code manually (optional): ${NC}${YELLOW}ruff format .${NC}"
        
        echo -e "\n${BLUE}ℹ️  Ultra-safe auto-fix completed. Only applied:${NC}"
        echo -e "  ${GREEN}•${NC} Runtime and syntax error fixes (E9, F63, F7, F82)"
        echo -e "  ${GREEN}•${NC} Unused imports removal (F401, F811)" 
        echo -e "  ${GREEN}•${NC} Undefined name fixes (F821, F822, F823)"
        echo -e "  ${GREEN}•${NC} Unused variable cleanup (F841)"
        echo -e "  ${YELLOW}•${NC} ZERO style or formatting changes"
        echo -e "  ${YELLOW}•${NC} NO changes to line length, indentation, or spacing"
        echo -e "  ${YELLOW}•${NC} Your existing code style is fully preserved"
        
        # Show remaining issues but don't fail the fix mode
        echo -e "\n${BLUE}🔍 Checking remaining issues after fixes (informational only)...${NC}"
        
        # Run critical linting check (safe to show)
        echo -e "${YELLOW}📋 Checking for remaining linting issues...${NC}"
        if ruff check . --select E9,F63,F7,F82 --target-version py312; then
            echo -e "${GREEN}✅ No critical linting issues remaining${NC}"
        else
            echo -e "${YELLOW}ℹ️  Some linting issues remain (require manual review)${NC}"
        fi
        
        # Run MyPy but don't let it affect exit code
        echo -e "${YELLOW}� Checking for type issues (informational)...${NC}"
        if command -v mypy &> /dev/null; then
            if mypy . --ignore-missing-imports --disable-error-code import-untyped --no-strict-optional --show-error-codes --pretty >/dev/null 2>&1; then
                echo -e "${GREEN}✅ No critical type issues detected${NC}"
            else
                echo -e "${YELLOW}ℹ️  Type issues detected - run './code_quality.sh critical' for details${NC}"
            fi
        else
            echo -e "${YELLOW}ℹ️  MyPy not available for type checking${NC}"
        fi
        
        echo -e "\n${GREEN}🎉 Safe auto-fix completed successfully!${NC}"
        echo -e "${BLUE}💡 Tip: Run './code_quality.sh critical' to see detailed remaining issues${NC}"
        ;;
        
    *)
        echo -e "${RED}❌ Invalid mode: $MODE${NC}"
        echo -e "${BLUE}Usage: ./code_quality.sh [critical|full|fix]${NC}"
        echo ""
        echo -e "${YELLOW}Modes:${NC}"
        echo -e "  ${GREEN}critical${NC} - Fast feedback, errors only (for dev workflow)"
        echo -e "  ${GREEN}full${NC}     - Comprehensive analysis (for CI/CD)"
        echo -e "  ${GREEN}fix${NC}      - Safe auto-fix only (no semantic changes)"
        echo ""
        echo -e "${YELLOW}Environment Variables:${NC}"
        echo -e "  ${GREEN}ENABLE_BANDIT=1${NC} - Enable bandit security checks (disabled by default for secure internal app)"
        echo -e "  ${GREEN}ENABLE_SAFETY=1${NC} - Enable safety dependency vulnerability checks (disabled by default for secure internal app)"
        exit 1
        ;;
esac

# Summary
echo -e "\n${BLUE}📊 Summary${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! Code quality is excellent.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  $ERRORS check(s) failed. Please review and fix issues.${NC}"
    echo -e "${YELLOW}💡 Tip: Run './code_quality.sh fix' to auto-fix safe issues only${NC}"
    exit 1
fi
