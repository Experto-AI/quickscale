"""Reusable wiring-parity harness for manifest-vs-legacy spec comparison.

Shared helper imported by per-module wiring-parity test files (C1 billing
through C7 forms).  Compares the output of the legacy flat-mapper builder
(``MODULE_WIRING_BUILDERS`` dispatch in ``module_wiring_specs.py``) against the
manifest-driven ``build_manifest_wiring_spec`` entry point and asserts FULL
:class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Equality checks cover:
    - ``apps``               (tuple, order matters)
    - ``middleware``         (tuple, order matters)
    - ``settings``           (dict, incl. nested values)
    - ``url_includes``       (tuple of 2-tuples, order matters)
    - ``pre_home_url_includes`` (tuple of 2-tuples, order matters)
    - ``managed_files``      (dict)

Usage
-----
Each per-module test file imports :func:`assert_wiring_parity` and calls it
with a list of options-dicts to probe.  Pass the module name string and an
iterable of options dicts; each dict is compared independently.

Example::

    from quickscale_cli.tests.wiring_parity import assert_wiring_parity

    def test_billing_parity_defaults():
        assert_wiring_parity("billing", [{}])

    def test_billing_parity_overrides():
        assert_wiring_parity("billing", [
            {"billing_currency": "eur"},
            {"enabled": False},
        ])
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_core.manifest.entry_point import build_manifest_wiring_spec
from quickscale_cli.commands.module_wiring_specs import MODULE_WIRING_BUILDERS


def _get_legacy_spec(module_name: str, options: dict[str, Any]) -> ModuleWiringSpec:
    """Return the spec produced by the legacy flat-mapper builder.

    Args:
        module_name: Name of the module (e.g. ``"billing"``).
        options: Options dict to pass to the builder.

    Returns:
        The :class:`~quickscale_core.module_wiring.ModuleWiringSpec` produced
        by the legacy builder.

    Raises:
        KeyError: When no legacy builder is registered for *module_name*.
    """
    builder = MODULE_WIRING_BUILDERS[module_name]
    return builder(options)


def _get_manifest_spec(
    module_name: str,
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Return the spec produced by the manifest-driven path.

    Args:
        module_name: Name of the module.
        options: Options dict to pass to the adapter.
        project_package: Optional project package name (unused for most modules).

    Returns:
        The :class:`~quickscale_core.module_wiring.ModuleWiringSpec` produced
        by the manifest-driven adapter.
    """
    return build_manifest_wiring_spec(
        module_name,
        options,
        project_package=project_package,
    )


def _diff_spec(
    legacy: ModuleWiringSpec,
    manifest: ModuleWiringSpec,
) -> list[str]:
    """Return a list of human-readable differences between two specs.

    Returns an empty list when the specs are equal.

    Args:
        legacy: The spec from the legacy builder.
        manifest: The spec from the manifest-driven path.

    Returns:
        List of difference descriptions; empty when equal.
    """
    diffs: list[str] = []

    if legacy.apps != manifest.apps:
        diffs.append(
            f"apps mismatch:\n  legacy  = {legacy.apps!r}\n  manifest= {manifest.apps!r}"
        )

    if legacy.middleware != manifest.middleware:
        diffs.append(
            f"middleware mismatch:\n  legacy  = {legacy.middleware!r}\n"
            f"  manifest= {manifest.middleware!r}"
        )

    if dict(legacy.settings) != dict(manifest.settings):
        legacy_keys = set(legacy.settings.keys())
        manifest_keys = set(manifest.settings.keys())
        missing_from_manifest = legacy_keys - manifest_keys
        extra_in_manifest = manifest_keys - legacy_keys
        differing_values = {
            k
            for k in legacy_keys & manifest_keys
            if legacy.settings[k] != manifest.settings[k]
        }
        if missing_from_manifest:
            diffs.append(
                f"settings keys missing from manifest: {sorted(missing_from_manifest)}"
            )
        if extra_in_manifest:
            diffs.append(
                f"settings keys extra in manifest: {sorted(extra_in_manifest)}"
            )
        for k in sorted(differing_values):
            diffs.append(
                f"settings[{k!r}] mismatch:\n"
                f"  legacy  = {legacy.settings[k]!r}\n"
                f"  manifest= {manifest.settings[k]!r}"
            )

    if legacy.url_includes != manifest.url_includes:
        diffs.append(
            f"url_includes mismatch:\n  legacy  = {legacy.url_includes!r}\n"
            f"  manifest= {manifest.url_includes!r}"
        )

    if legacy.pre_home_url_includes != manifest.pre_home_url_includes:
        diffs.append(
            f"pre_home_url_includes mismatch:\n  legacy  = {legacy.pre_home_url_includes!r}\n"
            f"  manifest= {manifest.pre_home_url_includes!r}"
        )

    if dict(legacy.managed_files) != dict(manifest.managed_files):
        diffs.append(
            f"managed_files mismatch:\n  legacy  = {dict(legacy.managed_files)!r}\n"
            f"  manifest= {dict(manifest.managed_files)!r}"
        )

    return diffs


def assert_wiring_parity(
    module_name: str,
    options_cases: Iterable[dict[str, Any]],
    *,
    project_package: str | None = None,
) -> None:
    """Assert that legacy and manifest-driven specs are equal for every options case.

    Runs :class:`~quickscale_core.module_wiring.ModuleWiringSpec` full
    dataclass equality comparison for each options dict in *options_cases*,
    printing a human-readable diff on failure.

    Args:
        module_name: Module name to compare (e.g. ``"billing"``).
        options_cases: Iterable of options dicts.  Each is tested independently.
        project_package: Optional project package name forwarded to the
            manifest adapter (unused for most modules).

    Raises:
        AssertionError: When any case fails parity.
    """
    for idx, options in enumerate(options_cases):
        legacy = _get_legacy_spec(module_name, options)
        manifest = _get_manifest_spec(
            module_name, options, project_package=project_package
        )
        diffs = _diff_spec(legacy, manifest)
        if diffs:
            formatted = "\n\n".join(diffs)
            raise AssertionError(
                f"Wiring-parity failure for module '{module_name}' at case[{idx}] "
                f"options={options!r}:\n\n{formatted}"
            )


__all__ = ["assert_wiring_parity"]
