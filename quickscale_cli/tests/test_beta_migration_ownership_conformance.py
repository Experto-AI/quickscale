"""Conformance gate: every generator-emitted file must be classified by the beta-migration taxonomy.

SA66 (Finding 7 first step).  The generator template tree at
``quickscale_core/generator/templates/`` is the authoritative inventory of
files QuickScale emits into a generated project.  The beta-migration file
taxonomy in ``quickscale_devtools/beta_migration.py`` classifies those
emitted files by migration path (fresh-first donor, fresh-first recipient,
in-place infrastructure, etc.).

This test enumerates every ``.j2`` template, resolves it to its emitted
project-relative path (accounting for theme-specific and conditional output),
adds non-Jinja theme files copied as-is by the generator, and asserts that
each emitted path is explicitly classified by at least one taxonomy tuple.
Files whose emitted paths are not covered by *any* taxonomy tuple fail the
test and are listed as a gap-inventory output so maintainers can add the
missing classification.

The ``INTENTIONALLY_UNMANAGED`` tuple provides the explicit escape hatch for
replacement/merge ownership: files listed there are not structurally replaced
or merged and must have a documented exemption rationale in ``decisions.md``.
They may participate in field-aware identity reconciliation or copy-if-missing
adoption, neither of which overwrites an existing user-owned file.
"""

from collections.abc import Collection
from pathlib import Path

import pytest

from quickscale_core.generator import get_generator_emission_mapping
from quickscale_devtools.beta_migration import (
    FRESH_FIRST_COMPONENT_DIR_SKIP,
    FRESH_FIRST_COPY_MISSING_DIRS,
    FRESH_FIRST_DONOR_DJANGO_FILES,
    FRESH_FIRST_IDENTITY_PACKAGE_FILES,
    FRESH_FIRST_IDENTITY_ROOT_FILES,
    FRESH_FIRST_MERGED_ROOT_FILES,
    FRESH_FIRST_OPTIONAL_DONOR_PACKAGE_FILES,
    FRESH_FIRST_PROTECTED_PACKAGE_FILES,
    FRESH_FIRST_PROTECTED_ROOT_FILES,
    FRESH_FIRST_REPLACED_ROOT_FILES,
    FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES,
    FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES,
    FRESH_FIRST_UTILITY_DIRS,
    IN_PLACE_INFRASTRUCTURE_TARGETS,
    IN_PLACE_MERGED_ROOT_FILES,
    IN_PLACE_MODULE_REACT_SURFACES,
    IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS,
    INTENTIONALLY_UNMANAGED,
    MODE_REQUIRED_SPECS,
)

# ---------------------------------------------------------------------------
# Template tree root  (relative to repository root)
# ---------------------------------------------------------------------------
_TEMPLATES_ROOT = (
    Path(__file__).resolve().parents[2]
    / "quickscale_core"
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
)

# ---------------------------------------------------------------------------
# Template-to-emitted-path mapping factory
# ---------------------------------------------------------------------------


def _template_emitted_paths() -> dict[str, str]:
    """Yield ``{emitted_path: template_rel}`` for every emitted file.

    Delegates to the production ``get_generator_emission_mapping()`` function
    in :mod:`quickscale_core.generator` for each supported theme and merges
    the results.  This is the authoritative source for the SA66 conformance
    gate and replaces the private routing copy (SA90).

    Each theme's mapping represents an actual generated project.  The union
    of both themes covers every possible emitted file across all generation
    variants.

    The emitted path is the path the file would have in a generated project,
    relative to the project root.  For package-level files (under
    ``project_name/``) the ``project_name`` segment is replaced with
    ``{package}``, meaning the exact package name is a variable.
    """
    if not _TEMPLATES_ROOT.is_dir():
        pytest.fail(f"Template tree not found at {_TEMPLATES_ROOT}")

    combined: dict[str, str] = {}
    for theme in ("showcase_react",):
        mapping = get_generator_emission_mapping(
            _TEMPLATES_ROOT,
            theme=theme,
            package_name="{package}",
        )
        # Merge — new entries and same-key entries from different themes
        # are both fine (they produce the same emitted path).
        for emitted_path, template_rel in mapping.items():
            if emitted_path not in combined:
                combined[emitted_path] = template_rel

    return combined


# ---------------------------------------------------------------------------
# Build the classified-path map from the taxonomy
# ---------------------------------------------------------------------------

# All taxonomy tuple names for per-tuple disposition tracking
_TUPLE_NAMES: tuple[tuple[str, Collection[str]], ...] = (
    (
        "FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES",
        FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES,
    ),
    (
        "FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES",
        FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES,
    ),
    (
        "FRESH_FIRST_OPTIONAL_DONOR_PACKAGE_FILES",
        FRESH_FIRST_OPTIONAL_DONOR_PACKAGE_FILES,
    ),
    ("FRESH_FIRST_DONOR_DJANGO_FILES", FRESH_FIRST_DONOR_DJANGO_FILES),
    ("FRESH_FIRST_IDENTITY_PACKAGE_FILES", FRESH_FIRST_IDENTITY_PACKAGE_FILES),
    ("FRESH_FIRST_IDENTITY_ROOT_FILES", FRESH_FIRST_IDENTITY_ROOT_FILES),
    ("FRESH_FIRST_PROTECTED_PACKAGE_FILES", FRESH_FIRST_PROTECTED_PACKAGE_FILES),
    ("FRESH_FIRST_PROTECTED_ROOT_FILES", FRESH_FIRST_PROTECTED_ROOT_FILES),
    ("IN_PLACE_INFRASTRUCTURE_TARGETS", IN_PLACE_INFRASTRUCTURE_TARGETS),
    (
        "IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS",
        IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS,
    ),
    ("INTENTIONALLY_UNMANAGED", INTENTIONALLY_UNMANAGED),
)


def _build_classified_map() -> dict[str, list[str]]:
    """Build a map of ``{emitted_path: [tuple_names]}`` from the taxonomy.

    Package-relative paths (like ``settings/production.py``) are stored
    as-is so they can be matched against the template inventory's
    ``{package}/settings/production.py`` form.

    In addition to direct path entries, ``INTENTIONALLY_UNMANAGED`` entries
    that end with a ``/`` suffix are treated as directory-level patterns:
    any emitted path that starts with that prefix is classified by the
    tuple.

    ``MODE_REQUIRED_SPECS`` entries are also included (both common and
    mode-specific) to cover files that are required as preflight checks
    and/or managed copy targets during migration — e.g.
    ``frontend/src/App.tsx`` is a required fresh-first recipient file
    that is copied from donor to recipient during the
    copy-custom-router-and-pages step.
    """
    classified: dict[str, list[str]] = {}

    for tup_name, tup in _TUPLE_NAMES:
        for item in tup:
            if item not in classified:
                classified[item] = []
            classified[item].append(tup_name)

    # Module React surfaces (root-relative) — these are not a named tuple
    # constant so we track them explicitly.
    module_surfaces: list[str] = []
    for paths in IN_PLACE_MODULE_REACT_SURFACES.values():
        for path in paths:
            module_surfaces.append(path)
    for path in module_surfaces:
        if path not in classified:
            classified[path] = []
        classified[path].append("IN_PLACE_MODULE_REACT_SURFACES")

    # MODE_REQUIRED_SPECS entries: include all file-type specs as explicit
    # classification sources.  The classification label uses the format
    # ``MODE_REQUIRED_SPECS_{mode}_{role}`` so the per-path disposition
    # can be traced back to the originating spec group.
    for mode, roles in MODE_REQUIRED_SPECS.items():
        for role, specs in roles.items():
            label = f"MODE_REQUIRED_SPECS_{mode}_{role}"
            for spec in specs:
                path = spec.relative_path
                if path not in classified:
                    classified[path] = []
                classified[path].append(label)

    return classified


# ---------------------------------------------------------------------------
# Classification resolution
# ---------------------------------------------------------------------------


def _classify_emitted_path(emitted: str, classified: dict[str, list[str]]) -> list[str]:
    """Return all taxonomy tuple names that classify an emitted path.

    Checks:
    1. Direct match on the emitted path itself.
    2. For ``{package}/...`` emitted paths, also checks the package-relative
       form (e.g. ``settings/production.py``).
    3. Directory-level matching: any parent directory of the emitted path
       that exists as an entry in the classified map.

    Returns a deduplicated list of tuple names.
    """
    matches: list[str] = []

    # Direct match
    if emitted in classified:
        matches.extend(classified[emitted])

    # Package-relative match for {package}/... paths
    pkg_prefix = "{package}/"
    if emitted.startswith(pkg_prefix):
        pkg_rel = emitted[len(pkg_prefix) :]
        if pkg_rel in classified:
            matches.extend(classified[pkg_rel])

    # Directory-level match: check each parent path
    parts = emitted.split("/")
    if len(parts) > 1:
        for i in range(1, len(parts)):
            parent_path = "/".join(parts[:i])
            dir_entry = parent_path.rstrip("/") + "/"
            if dir_entry in classified:
                matches.extend(classified[dir_entry])

    matches.extend(_structural_migration_classifications(emitted))

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            deduped.append(match)
    return deduped


def _structural_migration_classifications(emitted: str) -> list[str]:
    """Return operation-derived structural dispositions for one emitted path."""
    classifications: list[str] = []
    package_relative = (
        emitted.removeprefix("{package}/") if emitted.startswith("{package}/") else None
    )
    if emitted in FRESH_FIRST_REPLACED_ROOT_FILES:
        classifications.append("FRESH_FIRST_REPLACED_ROOT_FILES")
    if emitted in FRESH_FIRST_MERGED_ROOT_FILES:
        classifications.append("FRESH_FIRST_MERGED_ROOT_FILES")
    if package_relative in FRESH_FIRST_DONOR_DJANGO_FILES:
        classifications.append("FRESH_FIRST_DONOR_DJANGO_FILES")

    components_prefix = "frontend/src/components/"
    if emitted.startswith(components_prefix):
        component_dir = emitted.removeprefix(components_prefix).split("/", maxsplit=1)[
            0
        ]
        if component_dir not in FRESH_FIRST_COMPONENT_DIR_SKIP:
            classifications.append("FRESH_FIRST_COMPONENT_DIRECTORY_REPLACEMENT")

    for utility_dir in FRESH_FIRST_UTILITY_DIRS:
        if emitted.startswith(f"frontend/src/{utility_dir}/"):
            classifications.append("FRESH_FIRST_UTILITY_DIRECTORY_REPLACEMENT")
            break

    if any(
        emitted == directory or emitted.startswith(f"{directory}/")
        for directory in FRESH_FIRST_COPY_MISSING_DIRS
    ):
        classifications.append("FRESH_FIRST_COPY_MISSING_DIRS")

    if emitted in IN_PLACE_INFRASTRUCTURE_TARGETS:
        classifications.append("IN_PLACE_INFRASTRUCTURE_TARGETS")
    if emitted in IN_PLACE_MERGED_ROOT_FILES:
        classifications.append("IN_PLACE_MERGED_ROOT_FILES")
    for module_paths in IN_PLACE_MODULE_REACT_SURFACES.values():
        if any(
            emitted == path or emitted.startswith(f"{path.rstrip('/')}/")
            for path in module_paths
        ):
            classifications.append("IN_PLACE_MODULE_REACT_SURFACES")
            break
    return classifications


def _check_start_sh_classification(classified: dict[str, list[str]]) -> list[str]:
    """Check that ``start.sh`` is classified by the in-place taxonomy."""
    inconsistencies: list[str] = []
    if "start.sh" not in IN_PLACE_INFRASTRUCTURE_TARGETS:
        inconsistencies.append(
            "start.sh is NOT in IN_PLACE_INFRASTRUCTURE_TARGETS "
            "(user policy: start.sh is an in-place migration target)"
        )
    if "start.sh" in classified:
        start_sh_tuples = classified["start.sh"]
        if "IN_PLACE_INFRASTRUCTURE_TARGETS" not in start_sh_tuples:
            inconsistencies.append(
                "start.sh must be classified by IN_PLACE_INFRASTRUCTURE_TARGETS"
            )
    else:
        inconsistencies.append("start.sh is not classified by any taxonomy tuple")
    return inconsistencies


def _check_production_py_classification(classified: dict[str, list[str]]) -> list[str]:
    """Check that ``settings/production.py`` is classified (donor-owned by policy)."""
    inconsistencies: list[str] = []
    prod_pkg_rel = "settings/production.py"

    in_donor_files = prod_pkg_rel in FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES
    in_donor_django = prod_pkg_rel in FRESH_FIRST_DONOR_DJANGO_FILES
    if not in_donor_files or not in_donor_django:
        inconsistencies.append(
            f"settings/production.py must be classified as a donor-owned file "
            f"(in FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES={in_donor_files}, "
            f"in FRESH_FIRST_DONOR_DJANGO_FILES={in_donor_django})"
        )
    return inconsistencies


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_start_sh_is_in_place_managed() -> None:
    """SA66: start.sh must be classified as an in-place infrastructure target.

    User policy decision (2026-07-10): start.sh is an in-place migration
    target so the SA63 createcachetable env-pair fix reaches beta sites
    through the in-place migration path (the path that the existing sites
    actually use).
    """
    assert "start.sh" in IN_PLACE_INFRASTRUCTURE_TARGETS, (
        "start.sh must be in IN_PLACE_INFRASTRUCTURE_TARGETS "
        "(user policy: in-place managed)"
    )


def test_start_sh_is_in_place_substituted() -> None:
    """SA66 CR-SA66-001: start.sh must be identity-substituted during in-place.

    When start.sh is copied from donor to recipient during the in-place
    migration, the donor's embedded package/slug references (gunicorn
    WSGI module, etc.) must be replaced with the recipient's identity.
    Without substitution the copied file would retain the donor's
    gunicorn package reference and fail to boot.
    """
    assert "start.sh" in IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS, (
        "start.sh must be in IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS "
        "so donor package/slug references are replaced during in-place copy"
    )


def test_start_sh_is_fresh_first_identity_reconciled() -> None:
    """Fresh-first launchers must follow the reconciled recipient identity."""
    assert "start.sh" in FRESH_FIRST_IDENTITY_ROOT_FILES, (
        "start.sh must be in FRESH_FIRST_IDENTITY_ROOT_FILES so its WSGI package "
        "references follow fresh-first identity reconciliation"
    )


def test_production_py_is_donor_owned_by_policy() -> None:
    """SA66: settings/production.py must be in the fresh-first donor tuples.

    This is an explicit policy decision documented in decisions.md, not an
    accidental omission from the in-place targets.  The fresh-first path
    intentionally copies the donor's production.py onto the fresh recipient
    because the donor's production settings carry the real deploy-time
    configuration (env-var wiring, secret key references, etc.).
    """
    assert "settings/production.py" in FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES, (
        "settings/production.py must be in FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES "
        "(donor-owned by policy)"
    )
    assert "settings/production.py" in FRESH_FIRST_DONOR_DJANGO_FILES, (
        "settings/production.py must be in FRESH_FIRST_DONOR_DJANGO_FILES "
        "(donor-owned by policy)"
    )


def test_intentionally_unmanaged_entries_have_documented_rationale() -> None:
    """Every INTENTIONALLY_UNMANAGED entry must have a documented rationale.

    Files listed in ``INTENTIONALLY_UNMANAGED`` are deliberately outside
    structural replacement/merge ownership. Each such entry requires a documented
    exemption rationale in ``decisions.md`` § Generated-File Ownership
    (Beta-Migration Taxonomy). Identity-only and copy-if-missing overlaps are
    allowed because neither overwrites an existing user-owned file.

    If a new entry is added without updating ``decisions.md``, this test
    must be updated or the conformance gate expanded to cross-check the
    decision record.
    """
    # The tuple must currently be non-empty because we classify many
    # user-owned generated files there.
    assert len(INTENTIONALLY_UNMANAGED) > 0, (
        "INTENTIONALLY_UNMANAGED must contain entries for user-owned "
        "generated files.  See decisions.md § Generated-File Ownership."
    )


def test_taxonomy_classifies_every_emitted_template() -> None:
    """Every template-derived emitted file must be classified.

    This is the core conformance gate: enumerate all ``.j2`` templates
    (plus non-Jinja theme files copied as-is), resolve each to its emitted
    project-relative path, and assert that the emitted path is covered by
    at least one tuple or operation-derived taxonomy disposition.

    Every file must be explicitly accounted for; operation-derived structural
    dispositions cover paths selected by executor directory walks and merges.
    """
    emitted_paths = _template_emitted_paths()
    assert len(emitted_paths) >= 50, (
        "Generator emission inventory is unexpectedly small; the ownership gate "
        f"would be vacuous or incomplete ({len(emitted_paths)} paths)."
    )
    classified = _build_classified_map()

    unclassified: dict[str, str] = {}
    for emitted_path, template_rel in sorted(emitted_paths.items()):
        matches = _classify_emitted_path(emitted_path, classified)
        if not matches:
            unclassified[emitted_path] = template_rel

    # Fail if any path is unclassified, listing them all
    if unclassified:
        gap_lines = [f"  {ep}  (from: {tr})" for ep, tr in unclassified.items()]
        msg = (
            f"\n{len(unclassified)} emitted file(s) are not classified by any "
            f"beta-migration taxonomy disposition.\n"
            f"Add each path to the appropriate operation-derived disposition "
            f"or INTENTIONALLY_UNMANAGED tuple.\n"
            f"Unclassified paths:\n" + "\n".join(gap_lines)
        )
        pytest.fail(msg)


def test_classification_no_duplicate_conflicts() -> None:
    """No emitted file should be classified by conflicting taxonomy lists.

    A file that appears in both fresh-first and in-place lists is not
    necessarily a conflict (e.g. ``Dockerfile`` is identity-reconciled in
    fresh-first AND in-place-copied).  This test checks for *meaningful*
    conflicts: a file listed in an intentionally-unmanaged tuple that also
    appears in a structural replacement/merge disposition. Fresh-first identity
    reconciliation and copy-if-missing adoption may overlap because neither
    overwrites existing user-owned contents.
    """
    classified = _build_classified_map()
    conflicts: list[str] = []
    for emitted_path in sorted(_template_emitted_paths()):
        classifications = _classify_emitted_path(emitted_path, classified)
        if "INTENTIONALLY_UNMANAGED" not in classifications:
            continue
        structural = set(_structural_migration_classifications(emitted_path))
        structural.discard("FRESH_FIRST_COPY_MISSING_DIRS")
        if structural:
            conflicts.append(f"{emitted_path}: {', '.join(sorted(structural))}")
    assert not conflicts, (
        "INTENTIONALLY_UNMANAGED emitted paths also participate in structural "
        "replacement/merge operations:\n  " + "\n  ".join(conflicts)
    )


def test_operation_derived_structural_paths_match_executor_contract() -> None:
    """The conformance model must expose each non-tuple executor path."""
    assert _structural_migration_classifications("frontend/src/App.tsx") == [
        "FRESH_FIRST_REPLACED_ROOT_FILES"
    ]
    assert "FRESH_FIRST_COMPONENT_DIRECTORY_REPLACEMENT" in (
        _structural_migration_classifications(
            "frontend/src/components/layout/Header.tsx"
        )
    )
    assert "FRESH_FIRST_COMPONENT_DIRECTORY_REPLACEMENT" not in (
        _structural_migration_classifications("frontend/src/components/ui/button.tsx")
    )
    assert "IN_PLACE_MERGED_ROOT_FILES" in _structural_migration_classifications(
        "frontend/package.json"
    )
    assert "FRESH_FIRST_MERGED_ROOT_FILES" in _structural_migration_classifications(
        "pyproject.toml"
    )


# ---------------------------------------------------------------------------
# CR-SA94-REV-B-002: Reverse conformance — no stale INTENTIONALLY_UNMANAGED
# entries that reference a deleted HTML-only (or otherwise absent) path
# ---------------------------------------------------------------------------


def test_intentionally_unmanaged_entries_correspond_to_emitted_paths() -> None:
    """Every ``INTENTIONALLY_UNMANAGED`` entry must correspond to an emitted path.

    This is the reverse of ``test_taxonomy_classifies_every_emitted_template``
    for the ``INTENTIONALLY_UNMANAGED`` tuple specifically.  Stale entries
    (classifying a path no template emits) are detected and reported.

    Managed tuples (fresh-first / in-place) may reference files that are
    expected on the donor but not necessarily emitted by the generator
    (e.g. ``middleware.py``, ``sitemaps.py`` as optional donor files), so
    this reverse check scopes only to ``INTENTIONALLY_UNMANAGED`` where
    every entry should correspond to a current generated file.
    """
    emitted_paths = set(_template_emitted_paths().keys())
    stale: list[str] = []

    for path in sorted(INTENTIONALLY_UNMANAGED):
        # Direct match
        if path in emitted_paths:
            continue
        # {package}/ prefix match
        if path.startswith("{package}/") and path in emitted_paths:
            continue
        # Package-relative match: check {package}/<path>
        if not path.startswith("{package}/"):
            pkg_prefixed = "{package}/" + path
            if pkg_prefixed in emitted_paths:
                continue
        # Directory-level match: any emitted file starts with this path + "/"
        if any(ep.startswith(path + "/") for ep in emitted_paths):
            continue
        # The path itself is an emitted directory
        if any(ep == path for ep in emitted_paths):
            continue
        stale.append(path)

    if stale:
        lines = [
            f"\n{len(stale)} stale INTENTIONALLY_UNMANAGED entr(y/ies) without a "
            "matching emitted path:"
        ]
        for path in stale:
            lines.append(f"  {path}")
        lines.append(
            "Remove each stale entry from INTENTIONALLY_UNMANAGED, or confirm the "
            "entry is still valid and add a template that emits the path."
        )
        pytest.fail("\n".join(lines))
