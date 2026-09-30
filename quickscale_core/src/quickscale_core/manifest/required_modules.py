"""Required-module declaration parsing and transitive resolution.

A module's ``required_modules`` list holds **bare** first-party module names
(Module Conventions rule 39): version specifiers are retired because every
module ships in lockstep, and ``implies`` is gone because a required module
is selected together with its dependant.  This module owns both halves of
the declaration:

* :func:`parse_required_module_entry` validates one entry and returns its
  bare name.  The manifest loader refuses anything else (a specifier like
  ``orgs>=0.86.0``, an empty entry, a non-string), naming the rule.
* :func:`resolve_required_modules` computes the transitive closure of the
  required modules for a selected set, so ``plan`` and ``apply`` add every
  module a selected module depends on, through the source-tree manifests
  with the bundled snapshots as the installed-wheel fallback.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from pathlib import Path
from typing import Any, Pattern

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    get_bundled_manifests_path,
    get_modules_base_path,
)
from quickscale_core.manifest.loader import ManifestError, load_manifest_from_path

#: A first-party module name: a letter, then letters, digits, hyphens, or
#: underscores (the shape discovery uses for ``quickscale_modules/<name>/``).
_REQUIRED_MODULE_NAME_RE: Pattern[str] = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


def parse_required_module_entry(entry: str, module_name: str | None = None) -> str:
    """Return the bare module name a ``required_modules`` entry declares.

    Args:
        entry: A list entry, for example ``"orgs"``.
        module_name: Optional owning module name for error messages.

    Returns:
        The entry's bare module name (whitespace-stripped).

    Raises:
        ManifestError: When the entry is not a string, is empty, or carries a
            version specifier (retired under Module Conventions rule 39).
    """
    if not isinstance(entry, str):
        raise ManifestError(
            f"Invalid required_modules entry: {entry!r}. Expected a bare "
            "module name like 'orgs' (Module Conventions rule 39).",
            module_name,
        )
    stripped = entry.strip()
    if not stripped:
        raise ManifestError("required_modules entry must not be empty", module_name)
    if not _REQUIRED_MODULE_NAME_RE.match(stripped):
        raise ManifestError(
            f"Invalid required_modules entry: '{entry}'. Expected a bare "
            "module name like 'orgs'; version specifiers are retired "
            "(Module Conventions rule 39).",
            module_name,
        )
    return stripped


def resolve_required_modules(
    names: Collection[str],
    modules_base_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Resolve the transitive required-module closure from ``module.yml``.

    For each module name in *names*, load its manifest and examine its
    ``required_modules`` entries.  A required module not already selected is
    added to the result and itself scanned transitively, so every chain
    (for example billing → orgs → auth, notifications) is fully materialised
    and a cycle (orgs → auth, auth → orgs) terminates.

    A required module carries no configuration of its own, so each returned
    entry maps to an empty dict; callers merge it like any other module
    block and run their configurators over it.

    An initially selected name whose manifest cannot be found is skipped
    (the caller may pass names from other sources); a name required by a
    loaded manifest is a broken dependency when its own manifest is missing,
    so it fails hard even when it was also initially selected — it is never
    selected without a manifest to validate.

    Args:
        names: Module names already selected (e.g. from user config).
        modules_base_path: Directory containing ``<name>/module.yml``
            subdirectories.  Defaults to the maintainer's
            ``quickscale_modules/`` directory at the repository root,
            determined relative to this file's location in the package tree.
            When the source workspace is unavailable (installed-wheel
            context), falls back to the bundled manifest snapshots
            shipped within the ``quickscale_core`` package.

    Returns:
        A dict mapping each newly required module name to an empty config
        dict.  Only modules NOT already in *names* are returned.  Returns an
        empty dict when every requirement is already selected.

    Raises:
        ImproperlyConfigured: If no module manifest source is available
            (neither source-tree nor bundled manifests can be resolved).
        quickscale_core.manifest.loader.ManifestError: If a discovered
            required module has no manifest at its expected path, or a
            manifest is found but fails to load or validate.
        OSError: For I/O errors reading manifest files.
    """
    if modules_base_path is None:
        try:
            modules_base_path = get_modules_base_path()
            _bundled_fallback = False
        except ImproperlyConfigured:
            # SA113: fall back to bundled manifest snapshots when the
            # source-tree modules workspace is unavailable (installed
            # wheel context).  In this mode missing manifests are a
            # hard failure — the bundled snapshot is expected to be
            # complete.
            modules_base_path = get_bundled_manifests_path()
            _bundled_fallback = True
    else:
        _bundled_fallback = False

    selected: set[str] = set(names)
    required: dict[str, dict[str, Any]] = {}
    worklist: list[str] = list(names)

    while worklist:
        name = worklist.pop()
        manifest_path = modules_base_path / name / "module.yml"
        if not manifest_path.exists():
            if _bundled_fallback:
                raise ImproperlyConfigured(
                    f"Required module manifest not found in bundled "
                    f"snapshot: '{manifest_path}'.  The quickscale_core "
                    f"installation may be corrupted or incomplete."
                )
            # An initially selected name without a manifest is skipped; the
            # caller may pass names from other sources.
            continue

        manifest = load_manifest_from_path(manifest_path)

        for required_name in manifest.required_modules:
            required_path = modules_base_path / required_name / "module.yml"
            if not required_path.exists():
                # A loaded manifest's requirement with no manifest is a
                # broken dependency, whether or not the name was selected.
                if _bundled_fallback:
                    raise ImproperlyConfigured(
                        f"Required module manifest not found in bundled "
                        f"snapshot: '{required_path}'.  The quickscale_core "
                        f"installation may be corrupted or incomplete."
                    )
                raise ManifestError(
                    f"Required module '{required_name}' has no manifest at "
                    f"'{required_path}'.",
                    name,
                )
            if required_name not in selected:
                selected.add(required_name)
                required[required_name] = {}
                worklist.append(required_name)

    return required
