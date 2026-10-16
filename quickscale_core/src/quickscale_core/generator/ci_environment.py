"""The generated project's managed CI environment file (SA286).

The generated ``.github/workflows/ci.yml`` is user-owned, so it names no
module value: the non-live credentials an enabled module's startup check
reads in CI live in the managed ``.github/quickscale-ci-env`` file instead,
and the workflow loads it in one step.  Each module declares its placeholders
in its own ``module.yml`` ``ci_env`` section (declaring option -> placeholder);
the option's resolved value is the environment-variable name, so a project
that renames a variable through ``quickscale.yml`` keeps CI working without
editing a user-owned file, and a module release that changes a placeholder
reaches the project through ``apply``/``update`` alone.

Generation writes the file from the shipped manifests; ``quickscale apply``,
``quickscale update``, and ``quickscale remove`` regenerate it under the
managed-file hash guard beside the managed seam files (the path is part of
``quickscale_core.project_state_hashes.DEFAULT_MANAGED_PROJECT_PATHS``).

The workflow appends the file to GitHub Actions' ``$GITHUB_ENV`` file, which
reads ``NAME=value`` lines, so the content is exactly one such line per entry,
sorted by variable name, and no comments or blank lines; an empty mapping
renders an empty (zero-byte) file, which the load step appends harmlessly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)

__all__ = [
    "CI_ENVIRONMENT_RELATIVE_PATH",
    "ci_environment_entries",
    "render_ci_environment",
]

#: Project-relative path of the managed CI environment file.  Generation
#: emits it from :func:`render_ci_environment`, and ``apply``/``update``/
#: ``remove`` regenerate it under the managed-file hash guard, so a local
#: edit is reported as drift.
CI_ENVIRONMENT_RELATIVE_PATH = ".github/quickscale-ci-env"


def ci_environment_entries(
    module_names: Iterable[str] | None,
    options: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Return ``{environment-variable name: placeholder}`` for *module_names*.

    Each selected module's ``ci_env`` declaration resolves through the
    manifest engine with that module's supplied options (or its declared
    defaults), so the variable names follow the project's configured
    ``*_env_var`` values.  A declaration whose resolved name is blank
    contributes nothing: a blank name means the module reads no credential
    under it.  Two modules declaring the same variable name with different
    placeholders fail hard instead of silently resolving to one value.

    Args:
        module_names: The module selection; ``None`` means the whole shipped
            module set, and an empty iterable means no module.
        options: Configured module options keyed by module name; a module
            absent from the mapping resolves against its declared defaults.

    Returns:
        The resolved entries keyed by environment-variable name.

    Raises:
        ValueError: When two modules declare one variable name with
            different placeholder values.
    """
    if module_names is None:
        names = [entry.name for entry in MODULE_CATALOG]
    else:
        names = sorted(dict.fromkeys(module_names))
    resolved_options = options or {}
    entries: dict[str, str] = {}
    for module_name in names:
        manifest = load_module_manifest_with_fallback(module_name)
        if not manifest.ci_env:
            continue
        resolved = resolve_manifest_module_options(
            module_name, resolved_options.get(module_name)
        )
        for option_name, placeholder in manifest.ci_env.items():
            env_name = str(resolved.get(option_name) or "").strip()
            if not env_name:
                continue
            if any(char in env_name for char in "=\n\r "):
                raise ValueError(
                    f"CI environment variable name {env_name!r} resolved from "
                    f"{module_name}.{option_name} is not usable in a "
                    "NAME=value environment file; set the option to a name "
                    "without '=', whitespace, or a newline."
                )
            existing = entries.get(env_name)
            if existing is not None and existing != placeholder:
                raise ValueError(
                    f"CI environment variable {env_name!r} is declared with "
                    f"different placeholders ({existing!r} and {placeholder!r}); "
                    "rename one module's *_env_var option so each variable has "
                    "one owner."
                )
            entries[env_name] = placeholder
    return entries


def render_ci_environment(entries: Mapping[str, str]) -> str:
    """Render the managed CI environment file from resolved *entries*.

    Entries render sorted by variable name, so generation and
    ``apply``/``update`` agree on one content for one module set.  The file
    carries only ``NAME=value`` lines — one per entry, each newline-terminated
    — and is empty when no entry is declared (see the module docstring for
    why comments and blank lines are excluded).
    """
    return "".join(f"{name}={entries[name]}\n" for name in sorted(entries))
