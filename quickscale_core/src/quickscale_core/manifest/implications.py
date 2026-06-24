"""Generic transitive implication resolver for module manifests.

Resolves implied module dependencies declared via ``implies`` blocks in
``module.yml`` files.  The resolver loads each selected module's manifest,
walks its ``implies`` entries, and follows the chain transitively until
closure.  Modules already in the caller's selected set are excluded from the
output, emulating the classic hardcoded ladder that existed before this
resolver was extracted.
"""

from collections.abc import Collection
from pathlib import Path
from typing import Any

from quickscale_core.contracts.module_discovery import get_modules_base_path
from quickscale_core.manifest.loader import load_manifest_from_path


def resolve_module_implications(
    names: Collection[str],
    modules_base_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Resolve transitive module implications from ``module.yml`` manifests.

    For each module name in *names*, load its manifest and examine its
    ``implies`` entries.  Any implied module not already present in *names*
    is added to the result, and the new module is itself scanned
    transitively.  The process repeats until closure — every chain (e.g.
    billing → orgs → notifications) is fully materialised.

    Implied modules that are already in *names* are silently skipped so
    callers can merge the result without deduplication logic.

    Args:
        names: Module names already selected (e.g. from user config).
        modules_base_path: Directory containing ``<name>/module.yml``
            subdirectories.  Defaults to the maintainer's
            ``quickscale_modules/`` directory at the repository root,
            determined relative to this file's location in the package tree.

    Returns:
        A dict mapping each newly implied module name to its default
        config dict.  Only modules NOT already in *names* are returned.
        Returns an empty dict when there are no new implications.

    Raises:
        quickscale_core.manifest.loader.ManifestError: If a manifest is
            found but fails to load or validate.
        OSError: For I/O errors reading manifest files.
    """
    if modules_base_path is None:
        modules_base_path = get_modules_base_path()

    selected: set[str] = set(names)
    implied: dict[str, dict[str, Any]] = {}
    worklist: list[str] = list(names)

    while worklist:
        name = worklist.pop()
        manifest_path = modules_base_path / name / "module.yml"
        if not manifest_path.exists():
            continue

        manifest = load_manifest_from_path(manifest_path)

        for entry in manifest.implies:
            if entry.name not in selected:
                selected.add(entry.name)
                implied[entry.name] = dict(entry.default_config)
                worklist.append(entry.name)

    return implied
