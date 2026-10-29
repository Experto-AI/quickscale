"""Declared source-version range for the website migration path (SA277 a3).

A *source version* is the QuickScale release whose generator produced a donor
project.  The supported range is the running release plus the two preceding
minor releases; the website-migration smoke gate generates a donor at every
release in the declaration and proves the fresh-first workflow against it.
Earlier releases are generated from their release tags, while the running
release uses the checked-out generator, so a release being prepared is proven
before it ships.

The declaration is data, not an inference: it moves once per release, in the
same change that bumps ``VERSION``.  Validation fails closed when the newest
entry is not the running ``quickscale_core`` version, so a version bump cannot
quietly leave the gate testing an older window.

Projects older than the floor (for example ``bap-web``) are outside the
declared range; the prompt-driven port handles them.
"""

from __future__ import annotations

import re

from quickscale_core import __version__ as CURRENT_RELEASE_VERSION

_RELEASE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

#: Every QuickScale release whose generated projects the website migration path
#: supports, oldest first.  The last entry must equal the running release.
SUPPORTED_SOURCE_VERSIONS: tuple[str, ...] = ("0.87.0", "0.88.0", "0.89.0")


def parse_release_version(value: str) -> tuple[int, int, int]:
    """Return the numeric ``(major, minor, patch)`` tuple for ``value``.

    Anything but a plain ``X.Y.Z`` release string is rejected; the declaration
    never accepts a range expression or a prerelease label.
    """
    if not _RELEASE_VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"unsupported source version {value!r}: expected X.Y.Z")
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def validate_supported_source_versions() -> tuple[str, ...]:
    """Return the declaration after checking it against the running release.

    The tuple is the single source of truth for the supported window.  A
    duplicate, a descending pair, or a newest entry that has drifted from the
    running release is an error: extending the window is a deliberate release
    step, never a silent fallback to an older version.
    """
    versions = SUPPORTED_SOURCE_VERSIONS
    if not versions:
        raise ValueError("the supported source-version declaration is empty")
    parsed = [parse_release_version(version) for version in versions]
    if parsed != sorted(set(parsed)):
        raise ValueError(
            "the supported source versions must be unique and in ascending order: "
            f"{versions!r}"
        )
    if versions[-1] != CURRENT_RELEASE_VERSION:
        raise ValueError(
            "the supported source-version declaration must end at the running "
            f"release {CURRENT_RELEASE_VERSION!r}; add that release and drop the "
            f"oldest entry (declared: {versions!r})"
        )
    return versions


def supported_source_version_range() -> str:
    """Return the declared window as a lock-contract style range string."""
    versions = validate_supported_source_versions()
    major, minor, _patch = parse_release_version(versions[-1])
    return f">={versions[0]},<{major}.{minor + 1}.0"


def tag_generated_source_versions() -> tuple[str, ...]:
    """Return the declared versions generated from release tags, oldest first.

    The running release is generated from the checked-out generator instead,
    so it is excluded here even when a local tag happens to exist.
    """
    return tuple(
        version
        for version in validate_supported_source_versions()
        if version != CURRENT_RELEASE_VERSION
    )
