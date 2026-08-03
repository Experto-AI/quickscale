#!/usr/bin/env bash
# QuickScale installed-wheel venv provisioner wrapper (SA112a)
#
# Thin standalone entrypoint around the sourceable seam
# quickscale_provision_installed_venv (see scripts/_installed_wheel_venv.sh).
# On success stdout is exactly the absolute OUTPUT_DIR plus normal line
# termination; progress/tool chatter and the six [installed-wheel] markers go
# to stderr.  Usage/argument errors exit 2 with a diagnostic on stderr;
# provisioning failures exit non-zero (signal exits are 129/130/143 for
# HUP/INT/TERM).
#
# Usage:
#   ./scripts/provision_installed_venv.sh REPO_ROOT OUTPUT_DIR
#
# Exit codes:
#   0 — provisioned OUTPUT_DIR with an installed venv (venv/) and workdir (work/)
#   1 — provisioning failed (Python/Poetry missing or a build/install failure)
#   2 — usage or argument error

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./_installed_wheel_venv.sh
source "$ROOT/scripts/_installed_wheel_venv.sh"

usage() {
    echo "Usage: provision_installed_venv.sh REPO_ROOT OUTPUT_DIR" >&2
    echo "  REPO_ROOT   — absolute path to the repository root (VERSION + pyproject.toml)" >&2
    echo "  OUTPUT_DIR  — absolute path where the installed venv will be created" >&2
}

if [[ $# -ne 2 ]]; then
    usage
    exit 2
fi

repo_root="$1"
output_dir="$2"

if [[ "$repo_root" != /* ]]; then
    echo "ERROR: REPO_ROOT must be an absolute path: $repo_root" >&2
    usage
    exit 2
fi
if [[ "$output_dir" != /* ]]; then
    echo "ERROR: OUTPUT_DIR must be an absolute path: $output_dir" >&2
    usage
    exit 2
fi

quickscale_provision_installed_venv "$repo_root" "$output_dir"
