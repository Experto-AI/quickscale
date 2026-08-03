#!/usr/bin/env bash
# QuickScale installed-wheel venv provisioner (SA112a)
#
# Sourceable helper extracted from scripts/smoke_install.sh (SA110/SA111a).
# Builds all three QuickScale wheels (quickscale_core, quickscale_cli,
# quickscale) from per-run staged copies (never touches source pyproject.toml
# bytes), installs them into a throwaway venv under a caller-provided output
# directory, and creates an external workdir beside the venv.  Source-only —
# never run directly; both shipped callers (scripts/smoke_install.sh and
# scripts/provision_installed_venv.sh) source this file.
#
# Requires the caller to run with `set -euo pipefail` (both shipped callers
# do).  All progress/tool chatter and the six [installed-wheel] markers go to
# stderr; stdout carries exactly the absolute OUTPUT_DIR plus normal line
# termination on success, and nothing on failure.
#
# Public seam:
#   quickscale_provision_installed_venv REPO_ROOT OUTPUT_DIR
#
# Both arguments must be absolute.  REPO_ROOT must contain VERSION and
# pyproject.toml; OUTPUT_DIR must not exist, or must be an empty real
# directory — a regular file, symlink (including broken and
# directory-targeting links), or other non-directory node (FIFO, socket,
# device) is rejected with argument-error status 2 before any trap is armed
# or caller data touched.  A trailing slash is stripped, and the tested
# dot-component spellings (`/.`, `/./`, `//`, and a `name/..` that
# re-selects the same directory while every component exists) cannot
# bypass the shape checks: the symlink test applies to the final named
# component after dot-component resolution.  A `..` that cancels a
# nonexistent tail does not resume probing, so a later existing directory
# symlink reached through such a cancellation is not re-checked (F-005).
# Emptiness is checked only on a real directory (the helper never
# deletes pre-existing caller data, and a pre-existing empty directory
# becomes helper-owned once validation accepts it).  On success the helper
# transfers OUTPUT_DIR (containing venv/ and work/) to the caller and returns
# 0; on failure or signal it removes OUTPUT_DIR and exits non-zero (signal
# exits are 129/130/143 for HUP/INT/TERM).  Repeated calls in one shell are
# supported: every invocation resets its own allocation state first, so a
# failed or signaled run after a successful one never leaks its output class.
#
# The helper owns four allocation classes:
#   1. stage             — per-run staged package copies for building
#   2. Poetry build-venv — build venvs shared across staged builds
#   3. wheel collection  — collected built wheels from all staged builds
#   4. output            — the OUTPUT_DIR (installed venv + external workdir)
# Internal classes (1-3) are cleaned on every path; the output class is
# cleaned on failure/signal and transferred only after success.  The output
# class is adopted — and its cleanup state set — immediately after argument
# validation and trap arming, before prerequisite checks and internal
# allocation, so a failure or signal anywhere after validation cleans even a
# pre-existing empty OUTPUT_DIR.  Traps are armed before allocation; the
# helper is safe to call repeatedly in the same shell because every
# invocation resets its own allocation state first.  In
# the caller's own shell the caller's traps are restored on success and
# restored/dispatched on failure and signal, with the exact initiating status
# (see _qs_iv_cleanup / _qs_iv_restore_caller_traps / _qs_iv_trap_exit /
# _qs_iv_trap_signal).
#
# QS_SMOKE_REGRESSION_CORE (SA109): when set, quickscale_core is staged from
# that disposable copy instead of REPO_ROOT/quickscale_core.

if [[ -n "${QUICKSCALE_INSTALLED_WHEEL_VENV_LOADED:-}" ]]; then
    return 0
fi
QUICKSCALE_INSTALLED_WHEEL_VENV_LOADED=1

_QS_IV_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_python_requirement.sh
source "$_QS_IV_HELPER_DIR/_python_requirement.sh"

# ---- Allocation state (globals, not locals, so trap handlers see them) ----
# Post-allocation sentinels: each variable is set only after its directory is
# fully allocated, so _qs_iv_cleanup is deterministic at any signal boundary.
# All of these are reset at the start of every provisioner invocation, so a
# second call in the same shell never inherits the previous call's state.

_QS_IV_STAGE_DIR=""           # Allocation class 1 (per-run staged copies)
_QS_IV_BUILD_VENVS_DIR=""     # Allocation class 2 (Poetry build venvs)
_QS_IV_WHEEL_COLLECT_DIR=""   # Allocation class 3 (collected wheels)
_QS_IV_OUTPUT_DIR=""          # Allocation class 4 (caller output dir)
_QS_IV_OUTPUT_TRANSFERRED=0   # 1 once the output class was handed to the caller
_QS_IV_EXIT_STATUS=0          # Captured pending exit status for the EXIT trap
_QS_IV_CALLER_TRAP_EXIT=""    # Caller's EXIT trap registration (trap -p EXIT)
_QS_IV_CALLER_TRAP_HUP=""     # Caller's HUP trap registration (trap -p HUP)
_QS_IV_CALLER_TRAP_INT=""     # Caller's INT trap registration (trap -p INT)
_QS_IV_CALLER_TRAP_TERM=""    # Caller's TERM trap registration (trap -p TERM)

# ---- cleanup / traps ----

_qs_iv_cleanup() {
    local status=$?
    local class=""

    # Internal classes: cleaned on every path (success included).
    for class in "$_QS_IV_STAGE_DIR" "$_QS_IV_BUILD_VENVS_DIR" "$_QS_IV_WHEEL_COLLECT_DIR"; do
        if [[ -n "$class" ]] && [[ -d "$class" ]]; then
            rm -rf "$class"
        fi
    done

    # Output class: removed on failure/signal, kept after success transfer.
    if [[ -n "$_QS_IV_OUTPUT_DIR" ]] && [[ -d "$_QS_IV_OUTPUT_DIR" ]] \
        && [[ "$_QS_IV_OUTPUT_TRANSFERRED" != "1" ]]; then
        rm -rf "$_QS_IV_OUTPUT_DIR"
    fi

    # Record the captured status and always succeed: callers run under the
    # caller's `set -e`, and errexit is active inside trap handlers too, so a
    # non-zero return here would abort the EXIT/signal handler before it can
    # restore the caller's traps or pin the exit status.  The captured status
    # is read from _QS_IV_EXIT_STATUS by the trap handlers instead.
    _QS_IV_EXIT_STATUS="$status"
    return 0
}

_qs_iv_trap_exit() {
    _qs_iv_cleanup
    local status="$_QS_IV_EXIT_STATUS"

    # In the caller's own shell, restore the caller's traps and dispatch the
    # caller's EXIT trap with the initiating status.  Bash will not re-fire a
    # trap re-registered from inside the EXIT trap handler, so the dispatch
    # must be explicit (see _qs_iv_dispatch_caller_exit_trap).
    if [[ "$BASHPID" == "$$" ]]; then
        local exit_reg="$_QS_IV_CALLER_TRAP_EXIT"
        _qs_iv_restore_caller_traps
        _qs_iv_dispatch_caller_exit_trap "$exit_reg" "$status"
    fi

    exit "$status"
}

_qs_iv_trap_signal() {
    local signum="$1"
    _qs_iv_cleanup
    local status=$((128 + signum))

    # In the caller's own shell, restore the caller's traps before exiting so
    # bash natively fires the caller's EXIT trap with the signal status
    # (128 + signum).
    if [[ "$BASHPID" == "$$" ]]; then
        _qs_iv_restore_caller_traps
    fi

    exit "$status"
}

# Restore the caller's EXIT/HUP/INT/TERM traps that were saved before our own
# traps were armed.  Used on every path in the caller's own shell (success,
# failure, and signal) so the caller's traps are preserved no matter how the
# provisioner finishes.  Must only be called when BASHPID == $$: a
# command-substitution subshell cannot affect the caller's traps, and its
# inherited trap list must stay inert on subshell exit — restoring there
# would re-arm the caller's EXIT trap inside the subshell.
_qs_iv_restore_caller_traps() {
    local sig=""
    local var=""
    local reg=""

    for sig in EXIT HUP INT TERM; do
        var="_QS_IV_CALLER_TRAP_${sig}"
        reg="${!var:-}"
        if [[ -n "$reg" ]]; then
            eval "$reg"
        else
            trap - "$sig"
        fi
    done

    _QS_IV_CALLER_TRAP_EXIT=""
    _QS_IV_CALLER_TRAP_HUP=""
    _QS_IV_CALLER_TRAP_INT=""
    _QS_IV_CALLER_TRAP_TERM=""
}

# Return the given status so the next command observes it as $? (used to pin
# the initiating status for the caller's dispatched EXIT trap).
_qs_iv_set_status() {
    return "$1"
}

# Run the caller's saved EXIT trap command with $? pinned to the initiating
# status.  Only called from _qs_iv_trap_exit: bash does not re-fire a trap
# re-registered from inside the EXIT trap handler, so the caller's cleanup
# must be dispatched explicitly after the registration is restored.  errexit
# is suspended around the dispatch so neither the status pinning nor a failing
# trap command can abort the handler before the pinned exit; an explicit exit
# inside the trap command still wins, matching native trap semantics.
_qs_iv_dispatch_caller_exit_trap() {
    local reg="$1"
    local status="$2"
    local cmd=""
    local trap_cmd=""
    local errexit=""

    if [[ -z "$reg" ]]; then
        return 0
    fi

    # reg is "trap -- 'COMMAND' EXIT" as printed by trap -p; strip the
    # registration wrapper and unquote to recover the bare COMMAND.
    cmd="${reg#trap -- }"
    cmd="${cmd% EXIT}"
    eval "trap_cmd=$cmd"

    case "$-" in *e*) errexit=1 ;; esac
    set +e
    _qs_iv_set_status "$status"
    eval "$trap_cmd"
    if [[ -n "$errexit" ]]; then
        set -e
    fi
}

# ---- Python toolchain selection ----

# Check whether a Python interpreter satisfies the full requires-python spec
# (e.g. >=3.14,<3.15).  Returns 0 if the interpreter is within bounds, 1 if
# not.  Can be used as a filter predicate — does not call exit.
quickscale_installed_wheel_python_within_spec() {
    local python_bin="$1"
    local spec="$2"

    "$python_bin" -c "
import sys
spec = '$spec'
parts = [p.strip() for p in spec.split(',')]
min_str = parts[0].lstrip('>=')
max_str = parts[1].lstrip('<')
min_ver = tuple(int(x) for x in min_str.split('.'))
max_ver = tuple(int(x) for x in max_str.split('.'))
v = sys.version_info[:len(min_ver)]
sys.exit(0 if min_ver <= v < max_ver else 1)
"
}

# Read candidate Python interpreter paths from stdin (one per line), check
# each against the full requires-python spec, and return the first valid one.
# Continues past invalid candidates so a newer (e.g. 3.15) or too-old (e.g.
# 3.13) interpreter on the PATH does not prevent finding a valid one.
#
# Pipe-testable: passing known paths with controlled Python shims validates
# the selection order without needing actual 3.14/3.15 binaries.
#
#   printf '%s\n' /path/fake3.15 /path/python3.14 \
#       | quickscale_installed_wheel_select_python '>=3.14,<3.15'
quickscale_installed_wheel_select_python() {
    local spec="$1"
    local candidate
    local found=""

    while IFS= read -r candidate; do
        if [[ -z "$candidate" || ! -x "$candidate" ]]; then
            continue
        fi
        if quickscale_installed_wheel_python_within_spec "$candidate" "$spec"; then
            found="$candidate"
            break
        fi
    done

    if [[ -n "$found" ]]; then
        printf '%s\n' "$found"
        return 0
    fi
    return 1
}

# Select a Python interpreter that satisfies the full requires-python spec and
# record it in QUICKSCALE_IV_PYTHON_BIN / QUICKSCALE_IV_PYTHON_DISPLAY_VERSION.
# Iterates past invalid candidates so a 3.15 on PATH does not block finding a
# valid 3.14.  Exits 1 with a diagnostic on stderr when none matches.
quickscale_ensure_installed_wheel_python() {
    local root="$1"
    local spec=""
    local python_bin=""
    local found_ver=""
    local probe=""

    spec="$(quickscale_requires_python_spec "$root")"
    python_bin="$(quickscale_installed_wheel_select_python "$spec" \
        < <(quickscale_python_candidates "$root"))" || {
        # Try to extract a version from any candidate for the error message.
        while IFS= read -r probe; do
            if [[ -n "$probe" ]] && [[ -x "$probe" ]]; then
                found_ver="$("$probe" --version 2>&1 || echo "unknown")"
                break
            fi
        done < <(quickscale_python_candidates "$root" 2>/dev/null || printf '')
        echo "" >&2
        echo "❌ No Python interpreter satisfies requires-python spec: ${spec}" >&2
        if [[ -n "$found_ver" ]]; then
            echo "   Closest candidate: ${found_ver}" >&2
            echo "   (rejected — outside the required range)" >&2
        fi
        echo "" >&2
        exit 1
    }

    QUICKSCALE_IV_PYTHON_BIN="$python_bin"
    QUICKSCALE_IV_PYTHON_DISPLAY_VERSION="$(quickscale_python_major_minor "$python_bin")"
}

quickscale_ensure_installed_wheel_python_venv_available() {
    if "$QUICKSCALE_IV_PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import ensurepip
import venv
PY
    then
        return 0
    fi

    echo "" >&2
    echo "❌ Compatible Python ${QUICKSCALE_IV_PYTHON_DISPLAY_VERSION:-} was found at $QUICKSCALE_IV_PYTHON_BIN, but its venv/ensurepip modules are unavailable." >&2
    echo "" >&2
    exit 1
}

# Print the Poetry version to stdout; exit 1 with a diagnostic on stderr when
# Poetry is absent.
quickscale_ensure_installed_wheel_poetry_available() {
    if ! command -v poetry &> /dev/null; then
        echo "❌ Poetry is required but not installed." >&2
        exit 1
    fi
    poetry --version
}

# ---- staging / build / install ----

# Stage a package: copy its directory to the per-run staging area with
# pyproject.toml modifications applied to the copy (never touches the source
# tree).  Prints the staged path to stdout.
_qs_iv_stage_package() {
    local pkg_name="$1"       # directory basename under REPO_ROOT
    local version="$2"
    local needs_path_fix="$3" # "yes" to replace path deps; "no" otherwise
    local repo_root="$4"

    # Allow a disposable modified core source for SA109 regression testing.
    # Normal production use omits this env var entirely.
    local src_dir
    if [[ "$pkg_name" == "quickscale_core" && -n "${QS_SMOKE_REGRESSION_CORE:-}" ]]; then
        src_dir="$QS_SMOKE_REGRESSION_CORE"
    else
        src_dir="$repo_root/$pkg_name"
    fi
    local dst_dir="$_QS_IV_STAGE_DIR/$pkg_name"

    echo "  📦 Staging $pkg_name..." >&2

    # Copy the full package directory (excluding heavy build artifacts).
    # Using cp -a preserves symlinks and metadata.
    mkdir -p "$dst_dir"
    cp -a "$src_dir/." "$dst_dir/"

    # Remove artifacts that would bloat the stage and are not needed for build.
    rm -rf "$dst_dir/dist" "$dst_dir/__pycache__" "$dst_dir/.venv"
    find "$dst_dir" -name '*.pyc' -delete 2>/dev/null || true
    rm -f "$dst_dir/.quickscale_tmp_readme" "$dst_dir/.quickscale_tmp_pyproject_backup"
    rm -f "$dst_dir/pyproject.toml.backup"

    # Fix readme path so poetry can find README.md in the package dir.
    if [[ -f "$dst_dir/pyproject.toml" ]]; then
        sed -i 's|readme = "\.\./README\.md"|readme = "README.md"|' "$dst_dir/pyproject.toml"
    fi

    # Replace path dependencies with versioned ones for clean wheel builds.
    if [[ "$needs_path_fix" == "yes" ]]; then
        sed -Ei \
            "s|quickscale-core = \{path = \"\.\./quickscale_core\"(, develop = true)?\}|quickscale-core = \"^${version}\"|" \
            "$dst_dir/pyproject.toml"
    fi

    # Copy root README if the package does not have its own.
    if [[ -f "$repo_root/README.md" ]] && [[ ! -f "$dst_dir/README.md" ]]; then
        cp "$repo_root/README.md" "$dst_dir/README.md"
    fi

    printf '%s' "$dst_dir"
}

_qs_iv_ensure_poetry_uses_compatible_python() {
    local pkg_dir="$1"

    (
        cd "$pkg_dir"
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$_QS_IV_BUILD_VENVS_DIR" \
        poetry env use "$QUICKSCALE_IV_PYTHON_BIN" >/dev/null 2>&1
    )
}

_qs_iv_build_with_poetry() {
    local pkg_dir="$1"
    local venv_path

    venv_path="$(
        cd "$pkg_dir"
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$_QS_IV_BUILD_VENVS_DIR" \
        poetry env info -p
    )"

    (
        cd "$pkg_dir"
        VIRTUAL_ENV="$venv_path" \
        PATH="$venv_path/bin:$PATH" \
        POETRY_ACTIVE=1 \
        POETRY_VIRTUALENVS_CREATE=true \
        POETRY_VIRTUALENVS_IN_PROJECT=false \
        POETRY_VIRTUALENVS_PATH="$_QS_IV_BUILD_VENVS_DIR" \
        poetry build >&2
    )
}

# Build a staged package and copy the resulting wheel into the collection
# directory.  Modifies the staged copy in-place (which is temp and
# per-run — no source mutation).
_qs_iv_build_staged_package() {
    local pkg_name="$1"
    local staged_dir="$_QS_IV_STAGE_DIR/$pkg_name"

    echo "  🏗️  Building $pkg_name (staged)..." >&2
    _qs_iv_ensure_poetry_uses_compatible_python "$staged_dir"
    rm -rf "$staged_dir/dist"
    _qs_iv_build_with_poetry "$staged_dir"

    # Collect the wheel into the shared collection directory.
    mkdir -p "$_QS_IV_WHEEL_COLLECT_DIR"
    cp "$staged_dir"/dist/*.whl "$_QS_IV_WHEEL_COLLECT_DIR"/
}

_qs_iv_pip_install_isolated() {
    local venv_dir="$1"
    shift

    "$venv_dir/bin/python" -E -m pip install \
        --disable-pip-version-check \
        --force-reinstall \
        "$@"
}

_qs_iv_read_version() {
    local root="$1"
    local version_file="$root/VERSION"

    if [[ -f "$version_file" ]]; then
        tr -d '\r' < "$version_file" | sed -e 's/^\s*//' -e 's/\s*$//'
    else
        echo "ERROR: VERSION file not found at $version_file" >&2
        exit 1
    fi
}

# ---- public seam ----

# Build and install all three QuickScale wheels into OUTPUT_DIR/venv and
# create the external OUTPUT_DIR/work dir.  On success stdout is exactly the
# absolute OUTPUT_DIR plus normal line termination; progress/tool chatter and
# the six [installed-wheel] markers go to stderr.  The output class is adopted
# right after argument validation and trap arming, so on failure or signal —
# including failures and signals before the internal classes are allocated —
# it is removed and the process exits non-zero (HUP=129, INT=130, TERM=143).
# In the caller's own shell the caller's traps are restored on success and
# restored/dispatched on failure and signal.
quickscale_provision_installed_venv() {
    local repo_root="$1"
    local output_dir="$2"
    local version=""
    local venv_dir=""
    local work_dir=""
    local pkg=""
    local needs_path_fix=""

    # ---- Reset per-invocation state before traps/allocation ----
    # The helper is sourceable, so a second call in the same shell must not
    # inherit the previous call's allocation state or output-transfer flag:
    # a success followed by failure/signal would otherwise treat the new
    # output class as already transferred and leak it.
    _QS_IV_STAGE_DIR=""
    _QS_IV_BUILD_VENVS_DIR=""
    _QS_IV_WHEEL_COLLECT_DIR=""
    _QS_IV_OUTPUT_DIR=""
    _QS_IV_OUTPUT_TRANSFERRED=0
    _QS_IV_EXIT_STATUS=0
    _QS_IV_CALLER_TRAP_EXIT=""
    _QS_IV_CALLER_TRAP_HUP=""
    _QS_IV_CALLER_TRAP_INT=""
    _QS_IV_CALLER_TRAP_TERM=""

    # ---- Argument validation (caller traps are still untouched here) ----
    if [[ "$repo_root" != /* ]]; then
        echo "ERROR: REPO_ROOT must be an absolute path: $repo_root" >&2
        exit 2
    fi
    if [[ "$output_dir" != /* ]]; then
        echo "ERROR: OUTPUT_DIR must be an absolute path: $output_dir" >&2
        exit 2
    fi
    if [[ ! -f "$repo_root/VERSION" ]]; then
        echo "ERROR: VERSION file not found at $repo_root/VERSION" >&2
        exit 2
    fi
    if [[ ! -f "$repo_root/pyproject.toml" ]]; then
        echo "ERROR: pyproject.toml not found at $repo_root/pyproject.toml" >&2
        exit 2
    fi
    # F-005: enforce the OUTPUT_DIR argument-shape invariant before any trap
    # is armed, so a regular file, symlink (including broken or
    # directory-targeting links), or other non-directory node (FIFO, socket,
    # device) is rejected with argument-error status 2 and an empty stdout
    # instead of passing validation and failing later with a different status
    # (or, for a directory-targeting link, writing through the link into an
    # unowned target).  Emptiness is checked only on a real directory;
    # pre-existing caller data is never touched.
    #
    # The checks run against a component walk that mirrors mkdir -p while
    # every component exists: trailing slashes are stripped, `.` components
    # are skipped, `..` components pop the resolved path, existing
    # components are canonicalized with realpath, and a nonexistent tail is
    # appended textually.  The tested dot-component spellings — `/link/.`,
    # `/link/./`, `/link//`, and `/link/sub/..` — all fail the symlink test
    # against the final named component, exactly like `/link` itself.  This
    # is not complete `name/..` handling: a `..` that cancels a nonexistent
    # tail does not resume probing, so a later existing directory symlink
    # reached through such a cancellation is not re-checked (F-005).
    # Symlinks earlier in the path are traversed like any other parent
    # directory, matching the "empty real directory" contract.  On acceptance
    # the canonical resolved path replaces the argument, so the later
    # mkdir -p, adoption, and cleanup never operate on a `/.`-style spelling
    # (GNU rm refuses to remove such a path).
    while [[ "$output_dir" == */ && "$output_dir" != "/" ]]; do
        output_dir="${output_dir%/}"
    done
    local -a _qs_iv_named=()         # resolved path per named component (stack)
    local -a _qs_iv_named_link=()    # 1 when that component is a symlink
    local _qs_iv_remainder="$output_dir"
    local _qs_iv_component=""
    local _qs_iv_real="/"
    local _qs_iv_resolved=""
    local _qs_iv_is_link=0
    local _qs_iv_probe=1             # 1 while every component still exists
    while [[ -n "$_qs_iv_remainder" ]]; do
        _qs_iv_component="${_qs_iv_remainder%%/*}"
        if [[ "$_qs_iv_component" == "$_qs_iv_remainder" ]]; then
            _qs_iv_remainder=""
        else
            _qs_iv_remainder="${_qs_iv_remainder#*/}"
        fi

        if [[ -z "$_qs_iv_component" || "$_qs_iv_component" == "." ]]; then
            continue
        fi
        if [[ "$_qs_iv_component" == ".." ]]; then
            if [[ "${#_qs_iv_named[@]}" -gt 0 ]]; then
                unset '_qs_iv_named[-1]' '_qs_iv_named_link[-1]'
            fi
            if [[ "$_qs_iv_real" != "/" ]]; then
                _qs_iv_real="${_qs_iv_real%/*}"
                [[ -z "$_qs_iv_real" ]] && _qs_iv_real="/"
            fi
            continue
        fi

        # Named component; the parent is canonical, so -e/-L here see exactly
        # the entry the argument names.
        if [[ "$_qs_iv_probe" == "1" ]] \
            && { [[ -e "$_qs_iv_real/$_qs_iv_component" || -L "$_qs_iv_real/$_qs_iv_component" ]]; }; then
            if [[ -L "$_qs_iv_real/$_qs_iv_component" ]]; then
                _qs_iv_is_link=1
            else
                _qs_iv_is_link=0
            fi
            _qs_iv_named+=("$_qs_iv_real/$_qs_iv_component")
            _qs_iv_named_link+=("$_qs_iv_is_link")
            _qs_iv_resolved="$(realpath "$_qs_iv_real/$_qs_iv_component" 2>/dev/null || true)"
            if [[ -n "$_qs_iv_resolved" ]]; then
                _qs_iv_real="$_qs_iv_resolved"
            else
                # Broken symlink (exists as a link but resolves to nothing).
                _qs_iv_real="$_qs_iv_real/$_qs_iv_component"
            fi
        else
            # Nonexistent (or past the first nonexistent component): the tail
            # will be created as real directories by mkdir -p, so it is
            # appended textually and probing stops.
            _qs_iv_real="$_qs_iv_real/$_qs_iv_component"
            _qs_iv_named+=("$_qs_iv_real")
            _qs_iv_named_link+=(0)
            _qs_iv_probe=0
        fi
    done

    # The final named component after dot-component resolution is the node
    # mkdir -p will treat as OUTPUT_DIR; a symlink there is rejected while
    # the walk is still probing.  A leaf reached only through `..`
    # cancellation of a nonexistent tail is not re-checked (F-005).
    if [[ "${_qs_iv_named_link[-1]:-0}" == "1" ]]; then
        echo "ERROR: OUTPUT_DIR must not be a symlink: $output_dir" >&2
        exit 2
    fi
    if [[ -e "$_qs_iv_real" ]] && [[ ! -d "$_qs_iv_real" ]]; then
        echo "ERROR: OUTPUT_DIR exists but is not a directory: $output_dir" >&2
        exit 2
    fi
    if [[ -d "$_qs_iv_real" ]] && [[ -n "$(ls -A "$_qs_iv_real" 2>/dev/null || true)" ]]; then
        echo "ERROR: OUTPUT_DIR must not exist or must be empty: $output_dir" >&2
        exit 2
    fi
    # Canonicalize for the downstream mkdir -p / adoption / cleanup, so no
    # `/.`-style spelling survives into rm -rf.
    output_dir="$_qs_iv_real"

    # ---- Save the caller's traps; arm our own before allocation ----
    # The registrations are kept in globals so the trap handlers can restore
    # (and, for EXIT, dispatch) them on the failure and signal paths too.
    _QS_IV_CALLER_TRAP_EXIT="$(trap -p EXIT)"
    _QS_IV_CALLER_TRAP_HUP="$(trap -p HUP)"
    _QS_IV_CALLER_TRAP_INT="$(trap -p INT)"
    _QS_IV_CALLER_TRAP_TERM="$(trap -p TERM)"
    trap _qs_iv_trap_exit EXIT
    trap '_qs_iv_trap_signal 1' HUP
    trap '_qs_iv_trap_signal 2' INT
    trap '_qs_iv_trap_signal 15' TERM

    # ---- Adopt the output class before any post-validation work ----
    # F-003: a pre-existing empty OUTPUT_DIR becomes helper-owned as soon as
    # argument validation has accepted it, so a failure or signal before the
    # internal classes are allocated still cleans the output class instead of
    # leaving the accepted directory behind.
    _QS_IV_OUTPUT_DIR="$output_dir"
    mkdir -p "$_QS_IV_OUTPUT_DIR"

    # ---- Version and toolchain ----
    version="$(_qs_iv_read_version "$repo_root")"
    quickscale_ensure_installed_wheel_python "$repo_root"
    quickscale_ensure_installed_wheel_python_venv_available
    quickscale_ensure_installed_wheel_poetry_available >/dev/null

    # ---- Allocate the internal classes (stage, build venvs, wheels) ----
    _QS_IV_STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/quickscale-iv-stage-XXXXXX")"
    _QS_IV_BUILD_VENVS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/quickscale-iv-build-venvs-XXXXXX")"
    _QS_IV_WHEEL_COLLECT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/quickscale-iv-wheels-XXXXXX")"

    # ---- Stage all packages ----
    # Modifications are applied only to the per-run staged copies; the source
    # tree's pyproject.toml bytes are never rewritten.
    _qs_iv_stage_package "quickscale_core" "$version" "no" "$repo_root" >/dev/null
    _qs_iv_stage_package "quickscale_cli"  "$version" "yes" "$repo_root" >/dev/null
    _qs_iv_stage_package "quickscale"      "$version" "no" "$repo_root" >/dev/null

    # ---- Build all packages ----
    # Order: quickscale_core → quickscale_cli (path dep on core) → quickscale.
    echo "[installed-wheel] BUILD quickscale_core==${version}" >&2
    _qs_iv_build_staged_package "quickscale_core"
    echo "[installed-wheel] BUILD quickscale_cli==${version}" >&2
    _qs_iv_build_staged_package "quickscale_cli"
    echo "[installed-wheel] BUILD quickscale==${version}" >&2
    _qs_iv_build_staged_package "quickscale"

    # ---- Create the throwaway venv inside the output class ----
    venv_dir="$_QS_IV_OUTPUT_DIR/venv"
    "$QUICKSCALE_IV_PYTHON_BIN" -m venv "$venv_dir" >&2

    # ---- Install the wheels into the venv ----
    # Order matches the build order: core → cli → umbrella.
    echo "[installed-wheel] INSTALL quickscale_core==${version}" >&2
    echo "[installed-wheel] INSTALL quickscale_cli==${version}" >&2
    echo "[installed-wheel] INSTALL quickscale==${version}" >&2
    _qs_iv_pip_install_isolated "$venv_dir" \
        "$_QS_IV_WHEEL_COLLECT_DIR/quickscale_core-"*.whl \
        "$_QS_IV_WHEEL_COLLECT_DIR/quickscale_cli-"*.whl \
        "$_QS_IV_WHEEL_COLLECT_DIR/quickscale-"*.whl >&2

    # ---- Create the external workdir inside the output class ----
    work_dir="$_QS_IV_OUTPUT_DIR/work"
    mkdir -p "$work_dir"

    # ---- Success: transfer the output class to the caller ----
    _QS_IV_OUTPUT_TRANSFERRED=1
    _qs_iv_cleanup

    # Restore the caller's traps when running in the caller's own shell (a
    # command-substitution subshell cannot affect the caller's traps and its
    # inherited trap list must stay inert on subshell exit — restoring there
    # would re-arm the caller's EXIT trap inside the subshell).
    if [[ "$BASHPID" == "$$" ]]; then
        _qs_iv_restore_caller_traps
    fi

    printf '%s\n' "$_QS_IV_OUTPUT_DIR"
    return 0
}
