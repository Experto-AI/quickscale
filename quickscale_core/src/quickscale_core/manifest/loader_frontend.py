"""Manifest parsing for a module's frontend resource contract (SA320).

Split out of :mod:`quickscale_core.manifest.loader_sections` so the section's
closed validation stays in a focused sibling while the loader facade re-exports
the parser for existing imports.
"""

from __future__ import annotations

import re
from typing import Any

from quickscale_core.manifest.loader_errors import ManifestError
from quickscale_core.manifest.schema import FrontendResources

#: The keys a top-level ``frontend_resources`` section may declare.
_FRONTEND_RESOURCES_KEYS = frozenset({"paths", "payload_types"})

#: A resource name the managed hook exports a constant for.
_FRONTEND_RESOURCE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

#: A payload type name the managed hook declares.
_FRONTEND_PAYLOAD_TYPE_NAME = re.compile(r"[A-Z][A-Za-z0-9]*\Z")

#: A payload field name.
_FRONTEND_PAYLOAD_FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

#: The TypeScript scalar types a declared payload field may use.
_FRONTEND_PAYLOAD_FIELD_TYPES = frozenset({"string", "number", "boolean"})

#: A module-relative API subpath: one or more non-empty ``/``-separated
#: segments ending in ``/``.  It is appended to the module's
#: ``moduleApiPaths`` base, so it never carries a leading slash, a scheme, a
#: query string, or a template placeholder.
_FRONTEND_RESOURCE_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/\Z")


def _parse_frontend_resource_path(
    resource: str, raw_path: Any, module_name: str | None
) -> str:
    """Validate one ``frontend_resources.paths`` entry and return its value."""
    if not isinstance(raw_path, str) or not raw_path:
        raise ManifestError(
            f"frontend_resources.paths.{resource} must be a non-empty string",
            module_name,
        )
    if _FRONTEND_RESOURCE_PATH.match(raw_path) is None:
        raise ManifestError(
            f"frontend_resources.paths.{resource} must be a module-relative "
            "API subpath ending in '/', with no leading slash, scheme, query, "
            f"or template placeholder (got {raw_path!r})",
            module_name,
        )
    if any(segment in {".", ".."} for segment in raw_path.split("/") if segment):
        raise ManifestError(
            f"frontend_resources.paths.{resource} must not carry a '.' or "
            f"'..' segment (got {raw_path!r})",
            module_name,
        )
    return raw_path


def _parse_frontend_payload_type(
    type_name: str, fields_raw: Any, module_name: str | None
) -> dict[str, str]:
    """Validate one ``frontend_resources.payload_types`` entry and return it."""
    if _FRONTEND_PAYLOAD_TYPE_NAME.match(type_name) is None:
        raise ManifestError(
            "frontend_resources.payload_types keys must be type names "
            "(a capital letter followed by letters and digits)",
            module_name,
        )
    if not isinstance(fields_raw, dict) or not fields_raw:
        raise ManifestError(
            f"frontend_resources.payload_types.{type_name} must be a "
            "non-empty mapping of field name to type",
            module_name,
        )
    fields: dict[str, str] = {}
    for field_name, field_type in fields_raw.items():
        if (
            not isinstance(field_name, str)
            or _FRONTEND_PAYLOAD_FIELD_NAME.match(field_name) is None
        ):
            raise ManifestError(
                f"frontend_resources.payload_types.{type_name} field names "
                "must be identifiers (letters, digits, and underscores, not "
                "starting with a digit)",
                module_name,
            )
        if (
            not isinstance(field_type, str)
            or field_type not in _FRONTEND_PAYLOAD_FIELD_TYPES
        ):
            allowed = ", ".join(sorted(_FRONTEND_PAYLOAD_FIELD_TYPES))
            raise ManifestError(
                f"frontend_resources.payload_types.{type_name}.{field_name} "
                f"must use one of {allowed} (got {field_type!r})",
                module_name,
            )
        fields[field_name] = field_type
    return fields


def _parse_frontend_resources(
    data: dict[str, Any], module_name: str | None
) -> FrontendResources | None:
    """Parse and validate the optional top-level ``frontend_resources`` section.

    The section declares the module's frontend resource contract: the API
    subpaths a user-owned page may fetch (relative to the module's
    ``moduleApiPaths`` base) and the payload types those responses carry.
    The generated project's managed ``quickscaleSeam.hooks.ts`` renders these
    declarations, so a module release that changes a subpath or a payload
    shape changes only that managed file, never a user-owned theme file.

    An empty section, an unknown key, a malformed subpath, or a payload field
    outside the supported TypeScript scalar types fails closed: an inert or
    silently ignored declaration would leave the user-owned file as the
    contract's real home.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        A :class:`FrontendResources` instance, or ``None`` when the section is
        absent.

    Raises:
        ManifestError: If the section is malformed.
    """
    raw_section = data.get("frontend_resources")
    if raw_section is None:
        return None

    if not isinstance(raw_section, dict):
        raise ManifestError("'frontend_resources' must be a mapping", module_name)

    unknown_keys = [key for key in raw_section if key not in _FRONTEND_RESOURCES_KEYS]
    if unknown_keys:
        allowed = ", ".join(sorted(_FRONTEND_RESOURCES_KEYS))
        raise ManifestError(
            f"'frontend_resources' declares unknown key '{unknown_keys[0]}' "
            f"(allowed: {allowed})",
            module_name,
        )

    paths_raw = raw_section.get("paths", {})
    if not isinstance(paths_raw, dict):
        raise ManifestError("'frontend_resources.paths' must be a mapping", module_name)
    paths: dict[str, str] = {}
    for resource, raw_path in paths_raw.items():
        if (
            not isinstance(resource, str)
            or _FRONTEND_RESOURCE_NAME.match(resource) is None
        ):
            raise ManifestError(
                "'frontend_resources.paths' keys must be resource names "
                "(letters, digits, and underscores, not starting with a digit)",
                module_name,
            )
        paths[resource] = _parse_frontend_resource_path(resource, raw_path, module_name)

    types_raw = raw_section.get("payload_types", {})
    if not isinstance(types_raw, dict):
        raise ManifestError(
            "'frontend_resources.payload_types' must be a mapping", module_name
        )
    payload_types: dict[str, dict[str, str]] = {}
    for type_name, fields_raw in types_raw.items():
        if not isinstance(type_name, str):
            raise ManifestError(
                "frontend_resources.payload_types keys must be type names",
                module_name,
            )
        payload_types[type_name] = _parse_frontend_payload_type(
            type_name, fields_raw, module_name
        )

    if not paths and not payload_types:
        raise ManifestError(
            "'frontend_resources' must declare at least one path or payload type",
            module_name,
        )

    return FrontendResources(paths=paths, payload_types=payload_types)
