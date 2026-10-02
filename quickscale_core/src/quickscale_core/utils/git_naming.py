"""Module slug validation and split naming conventions.

Owns the strict module-name allowlist and the canonical maintainer-side
module path, split branch, and split tag templates. Re-exported from
``quickscale_core.utils.git_utils``.
"""

import re

from quickscale_core.utils.git_errors import GitError

# Strict module-name allowlist: alphanumeric, hyphens, underscores; must start
# with an alphanumeric character.  This prevents path-traversal (``..``, ``/``),
# flag-injection (``-leading``), and shell-meta characters from reaching
# ``git subtree --prefix=`` or branch-name arguments.
_MODULE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_module_name(module_name: str) -> None:
    """Reject *module_name* unless it is a safe bare slug.

    Raises :class:`GitError` with an operator-facing message when the name is
    empty, contains path separators, starts with ``-``, or includes any
    character outside ``[a-zA-Z0-9_-]``.
    """
    if not module_name:
        raise GitError("Module name must not be empty")
    if not _MODULE_NAME_RE.match(module_name):
        raise GitError(
            f"Invalid module name {module_name!r}; "
            "expected a bare slug matching [a-zA-Z0-9][a-zA-Z0-9_-]*"
        )


def resolve_module_path(module_name: str) -> str:
    """Return the canonical maintainer-side module path for *module_name*.

    Centralizes the ``quickscale_modules/<name>`` convention so split-publish
    callers do not hardcode the path template.  Raises :class:`GitError` when
    *module_name* is not a valid bare module slug (empty, path separators,
    ``..`` traversal, flag-injection prefixes, or shell-meta characters).
    """
    validate_module_name(module_name)
    return f"quickscale_modules/{module_name}"


def resolve_split_branch(module_name: str) -> str:
    """Return the canonical split branch name for *module_name*.

    Centralizes the ``splits/<name>-module`` convention so split-publish
    callers do not hardcode the branch template.  Raises :class:`GitError`
    when *module_name* is not a valid bare module slug (empty, path
    separators, ``..`` traversal, flag-injection prefixes, or shell-meta
    characters).
    """
    validate_module_name(module_name)
    return f"splits/{module_name}-module"


def resolve_split_tag(module_name: str, version: str) -> str:
    """Return the canonical immutable tag for a module split.

    Split tags use the split branch name as a namespace and the canonical
    three-component core version as their suffix.  The version parser is
    shared with manifest validation so tag construction cannot drift from the
    lockstep version contract.
    """
    # Keep this import lazy: publication wrapper smoke tests intentionally use
    # a minimal copied ``git_utils.py`` without the full manifest package.
    from quickscale_core.manifest.loader import _parse_canonical_version_triple

    try:
        major, minor, patch = _parse_canonical_version_triple(version)
    except (AttributeError, TypeError, ValueError) as e:
        raise GitError(f"Invalid canonical version {version!r}: {e}") from e
    return f"{resolve_split_branch(module_name)}/{major}.{minor}.{patch}"
