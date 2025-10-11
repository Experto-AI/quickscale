#!/usr/bin/env bash
# scripts/quickscale_legacy_symlink.sh
#
# Create or remove a symlink in this repository that points to a legacy
# QuickScale checkout outside the repo (default: ../quickscale-legacy).
#
# Usage:
#   ./scripts/quickscale_legacy_symlink.sh mount    # create the symlink (default source ../quickscale-legacy)
#   ./scripts/quickscale_legacy_symlink.sh unmount  # remove the symlink
#   ./scripts/quickscale_legacy_symlink.sh status   # show current status
#
# Options:
#   --source PATH       Path to the legacy folder (default: ../quickscale-legacy)
#   --link-name NAME    Name of link to create in repo root (default: quickscale-legacy)
#   --force             Force overwrite/remove when target exists
#   -h, --help          Show this help

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

SOURCE="../quickscale-legacy"
LINK_NAME="quickscale-legacy"
FORCE=0

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <mount|unmount|status> [--source PATH] [--link-name NAME] [--force]

Creates a symlink named "$LINK_NAME" in the repository root that points to a legacy
QuickScale directory outside the repo (default: ../quickscale-legacy). This is useful
so editors like VS Code and tools like GitHub Copilot can access the legacy code.

Examples:
  $SCRIPT_NAME mount
  $SCRIPT_NAME mount --source ../quickscalelegacy --link-name quickscalelegacy
  $SCRIPT_NAME unmount
  $SCRIPT_NAME status

Options:
  --source PATH     Path to the legacy folder (default: ../quickscale-legacy)
  --link-name NAME  Name of link to create in repo root (default: quickscale-legacy)
  --force           Force overwrite/remove when target exists
  -h, --help        Show this help
EOF
}

if [ $# -lt 1 ]; then
  usage
  exit 2
fi

COMMAND="$1"
shift || true

while [ $# -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE="$2"; shift 2;;
    --link-name)
      LINK_NAME="$2"; shift 2;;
    --force)
      FORCE=1; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown option: $1" >&2; usage; exit 2;;
  esac
done

# repo root (where this script lives's parent) should be used as cwd for link
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_PATH="$REPO_ROOT/$LINK_NAME"

realpath_or_fail() {
  if ! real="$(readlink -f -- "$1" 2>/dev/null)"; then
    return 1
  fi
  printf '%s' "$real"
}

mount_link() {
  if [ -z "$SOURCE" ]; then
    echo "Source path is empty" >&2; return 2
  fi

  if ! SOURCE_ABS="$(realpath_or_fail "$SOURCE")"; then
    echo "Error: source path does not exist: $SOURCE" >&2
    return 3
  fi

  # If target exists
  if [ -L "$TARGET_PATH" ]; then
    # existing symlink
    CURRENT="$(readlink -f -- "$TARGET_PATH")"
    if [ "$CURRENT" = "$SOURCE_ABS" ]; then
      echo "Symlink already exists and points to the desired source: $TARGET_PATH -> $SOURCE_ABS"
      return 0
    else
      if [ "$FORCE" -eq 1 ]; then
        echo "Removing existing symlink $TARGET_PATH (points to $CURRENT)"
        rm -f -- "$TARGET_PATH"
      else
        echo "Error: a symlink already exists at $TARGET_PATH pointing to $CURRENT" >&2
        echo "Use --force to overwrite." >&2
        return 4
      fi
    fi
  elif [ -e "$TARGET_PATH" ]; then
    # target exists and is not a symlink
    if [ "$FORCE" -eq 1 ]; then
      BACKUP="${TARGET_PATH}.$(date +%Y%m%d%H%M%S).bak"
      echo "Moving existing path $TARGET_PATH to backup $BACKUP"
      mv -- "$TARGET_PATH" "$BACKUP"
    else
      echo "Error: a file or directory already exists at $TARGET_PATH" >&2
      echo "Use --force to move it to a timestamped backup." >&2
      return 5
    fi
  fi

  ln -s -- "$SOURCE_ABS" "$TARGET_PATH"
  echo "Created symlink: $TARGET_PATH -> $SOURCE_ABS"
}

unmount_link() {
  if [ -L "$TARGET_PATH" ]; then
    CURRENT="$(readlink -f -- "$TARGET_PATH")"
    rm -f -- "$TARGET_PATH"
    echo "Removed symlink: $TARGET_PATH (was -> $CURRENT)"
    return 0
  fi

  if [ -e "$TARGET_PATH" ]; then
    if [ "$FORCE" -eq 1 ]; then
      echo "Force removing non-symlink path at $TARGET_PATH"
      rm -rf -- "$TARGET_PATH"
      echo "Removed $TARGET_PATH"
      return 0
    else
      echo "Error: $TARGET_PATH exists and is not a symlink. Use --force to remove it." >&2
      return 6
    fi
  fi

  echo "No symlink or file at $TARGET_PATH to remove.";
}

status_link() {
  echo "Repository root: $REPO_ROOT"
  echo "Link name: $LINK_NAME"
  echo "Intended target path: $TARGET_PATH"
  echo "Configured source: $SOURCE"
  if [ -L "$TARGET_PATH" ]; then
    echo "Status: symlink exists -> $(readlink -f -- "$TARGET_PATH")"
  elif [ -e "$TARGET_PATH" ]; then
    echo "Status: path exists but is NOT a symlink (type: $(file -b -- "$TARGET_PATH"))"
  else
    echo "Status: not present"
  fi
}

case "$COMMAND" in
  mount)
    mount_link; exit $? ;;
  unmount)
    unmount_link; exit $? ;;
  status)
    status_link; exit 0 ;;
  *)
    echo "Unknown command: $COMMAND" >&2; usage; exit 2 ;;
esac
