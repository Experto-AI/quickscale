"""SA49 — Derive orgs' cross-module conformance-env module list instead of
hand-listing it.

The orgs test suite (``tests/settings.py``) defines the cross-module
conformance environment used by tenant-registry coverage, FK-conformance,
purge-spec completeness, and other assertion gates.  Before this fix,
``INSTALLED_APPS`` was a hand-maintained list that could silently diverge
from the shipped module inventory — a new module with models would not
automatically appear in the conformance env, and the existing gates would
be blind to its tenant models and user-FKs.

This test derives the expected set of shipped QuickScale modules from
``quickscale_modules/*/pyproject.toml`` presence (the canonical packaging
marker), maps each to its Django app label, and asserts that every shipped
module with models is present in ``settings.INSTALLED_APPS``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from django.conf import settings


#: Repo-root-relative path to the modules workspace.
_MODULES_DIR: Final[str] = "quickscale_modules"

#: Django app-label prefix for QuickScale module apps.
_APP_PREFIX: Final[str] = "quickscale_modules_"

#: Shipped modules that are intentionally absent from the orgs conformance
#: environment because they contain no Django models.  These are safe to
#: exclude: any future addition of tenant-scoped models to these modules
#: would fail the assertion below, forcing a deliberate promotion.
#:
#: Keys are directory names (short form, e.g. ``"analytics"``).
_EXEMPT_NO_MODELS: frozenset[str] = frozenset(
    {
        "analytics",  # Analytics tag — no tenant-scoped models.
        "storage",  # Storage backend abstraction — no tenant-scoped models.
    }
)

#: Placeholder directories under ``quickscale_modules/`` that are not yet
#: shipped modules — they have no ``pyproject.toml`` and are skipped by
#: the derivation entirely.  Listed here for documentation only; the test
#: does not assert their presence or absence.
_PLACEHOLDER_DIRS: frozenset[str] = frozenset(
    {
        "teams",  # Placeholder — not yet packaged (no pyproject.toml).
    }
)


def _resolve_modules_root() -> Path:
    """Return the absolute path to the ``quickscale_modules/`` directory.

    Resolves relative to this test file::
        quickscale_modules/orgs/tests/test_sa49_conformance.py
    goes up 4 levels to the repo root, then into ``quickscale_modules/``.
    """
    return Path(__file__).resolve().parent.parent.parent.parent / _MODULES_DIR


def _shipped_module_dirs() -> list[Path]:
    """Return sorted list of shipped module directories under ``quickscale_modules/``.

    A module is considered *shipped* when its directory contains a
    ``pyproject.toml`` file (the canonical packaging marker used by
    Poetry and the existing ``check_module_core_compatibility.py``
    script).
    """
    modules_root = _resolve_modules_root()
    if not modules_root.is_dir():
        return []
    return sorted(
        entry
        for entry in modules_root.iterdir()
        if entry.is_dir() and (entry / "pyproject.toml").is_file()
    )


def _module_has_models(module_dir: Path) -> bool:
    """Return ``True`` if the module ships a ``models.py`` file.

    Checks for ``quickscale_modules_<name>/models.py`` inside the
    module's ``src/`` package tree.
    """
    name = module_dir.name
    src_models = module_dir / "src" / f"{_APP_PREFIX}{name}" / "models.py"
    return src_models.is_file()


def _module_app_label(module_dir: Path) -> str:
    """Derive the Django app label for a module directory.

    Convention: ``quickscale_modules_<directory_name>``.
    """
    return f"{_APP_PREFIX}{module_dir.name}"


# -----------------------------------------------------------------------
# CI conformance assertion
# -----------------------------------------------------------------------


def test_shipped_modules_with_models_in_installed_apps() -> None:
    """Every shipped module with models must be in the conformance env.

    Derives the expected module set from ``quickscale_modules/*/pyproject.toml``
    presence, then asserts that every module with a ``models.py`` file is
    present in ``settings.INSTALLED_APPS``.

    Modules without models (``analytics``, ``storage``) are exempt and
    listed as deliberate, named exceptions.  Placeholder directories
    without ``pyproject.toml`` (``teams``) are skipped entirely.

    If this test fails:
    *   A new module was added — add ``quickscale_modules_<name>`` to
        ``INSTALLED_APPS`` in ``tests/settings.py``.
    *   An existing module gained models — add it to ``INSTALLED_APPS``
        in ``tests/settings.py``.
    *   A module without models was intentionally added — add its
        directory name to ``_EXEMPT_NO_MODELS`` with a brief reason.
    """
    installed_labels: frozenset[str] = frozenset(settings.INSTALLED_APPS)

    missing: list[str] = []
    for mod_dir in _shipped_module_dirs():
        name = mod_dir.name

        has_models = _module_has_models(mod_dir)

        # Exempt modules that genuinely have no models are safe to skip.
        # If an exempt module now has models, fail with guidance to
        # remove the exemption and add the app to tests/settings.py.
        if name in _EXEMPT_NO_MODELS:
            if has_models:
                missing.append(
                    f"{name} (in _EXEMPT_NO_MODELS but has models.py; "
                    f"remove from _EXEMPT_NO_MODELS and add to "
                    f"tests/settings.py INSTALLED_APPS)"
                )
            continue

        if not has_models:
            # Module has pyproject.toml but no models.py — if it is not
            # in _EXEMPT_NO_MODELS, it needs either models or an exemption.
            missing.append(
                f"{name} (has pyproject.toml but no models.py; "
                f"add to _EXEMPT_NO_MODELS or add models)"
            )
            continue

        app_label = _module_app_label(mod_dir)
        if app_label not in installed_labels:
            missing.append(
                f"{name} → {app_label} (add to tests/settings.py INSTALLED_APPS)"
            )

    assert not missing, (
        "Shipped module(s) with models missing from the orgs conformance "
        "environment:\n" + "\n".join(f"  - {m}" for m in missing)
    )
