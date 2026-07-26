#!/usr/bin/env bash
# QuickScale installed-venv provisioner (SA112)
#
# Builds all wheels from per-run staged source copies (never touches source
# pyproject.toml), installs them into a caller-owned venv, and prints the
# path to the installed ``quickscale`` binary on stdout.
#
# All build/provision chatter is on stderr.  stdout is exactly one line:
# the absolute path to the installed quickscale binary.
#
# Usage:
#   QS_VENV="$(mktemp -d /tmp/my-venv-XXXXXX)"
#   QS_BIN="$(provision_installed_venv.sh "$QS_VENV")"
#   "$QS_BIN" --version
#   rm -rf "$QS_VENV"
#
# Exit codes:
#   0 — success; stdout is the quickscale binary path
#   1 — provisioning failed (see stderr)
#   2 — usage error

set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
    echo "ERROR: usage: provision_installed_venv.sh OUT_VENV_DIR" >&2
    exit 2
fi

_QS_PIV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_installed_wheel_venv.sh
source "$_QS_PIV_DIR/_installed_wheel_venv.sh"

iw_provision_installed_venv "$1"
