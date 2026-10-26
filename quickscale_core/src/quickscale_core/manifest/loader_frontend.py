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

#: A resource name the managed hook exports a constant or builder for.
_FRONTEND_RESOURCE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

#: One segment of a resource path: a literal segment or a ``{parameter}``
#: placeholder.  A placeholder is a whole segment, so the generated builder can
#: type it as one runtime value.
_FRONTEND_RESOURCE_SEGMENT = re.compile(
    r"(?:[A-Za-z0-9_.-]+|\{[A-Za-z_][A-Za-z0-9_]*\})\Z"
)

#: A ``{parameter}`` placeholder inside a resource path.
_FRONTEND_RESOURCE_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: A payload type name the managed hook declares.
_FRONTEND_PAYLOAD_TYPE_NAME = re.compile(r"[A-Z][A-Za-z0-9]*\Z")

#: A payload field name; a trailing ``?`` marks the field optional.
_FRONTEND_PAYLOAD_FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\??\Z")

#: The TypeScript atoms a declared field or union may use: the scalar
#: primitives, a declared type name, or a string-literal type.
_FRONTEND_TYPE_ATOM = (
    r"(?:string|number|boolean|[A-Z][A-Za-z0-9]*|'[A-Za-z][A-Za-z0-9_-]*')"
)

#: A field type: one atom, an array of it, or the atom made nullable.
_FRONTEND_FIELD_TYPE = re.compile(rf"{_FRONTEND_TYPE_ATOM}(?:\[\])?(?:\s*\|\s*null)?\Z")

#: A union type expression: two or more atoms.
_FRONTEND_UNION_TYPE = re.compile(
    rf"{_FRONTEND_TYPE_ATOM}(?:\s*\|\s*{_FRONTEND_TYPE_ATOM})+\Z"
)

#: A capitalized identifier inside a field or union expression.  It names a
#: payload type declared by the same module.
_FRONTEND_TYPE_REFERENCE = re.compile(r"[A-Z][A-Za-z0-9]*")

#: TypeScript reserved words that cannot be a builder parameter binding.
_TS_RESERVED_PARAMETER_NAMES = frozenset(
    {
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "implements",
        "import",
        "in",
        "instanceof",
        "interface",
        "let",
        "new",
        "null",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)


def _parse_frontend_resource_path(
    resource: str, raw_path: Any, module_name: str | None
) -> str:
    """Validate one ``frontend_resources.paths`` entry and return its value.

    A path is a module-relative API subpath: no leading slash, scheme, query
    string, or template placeholder, and at most one trailing slash.  A segment
    may be a ``{parameter}`` placeholder; the managed hook then renders a
    builder function instead of a string, so the path keeps one generated
    home even when it carries a runtime identifier.
    """
    if not isinstance(raw_path, str) or not raw_path:
        raise ManifestError(
            f"frontend_resources.paths.{resource} must be a non-empty string",
            module_name,
        )
    if raw_path.startswith("/"):
        raise ManifestError(
            f"frontend_resources.paths.{resource} must be a module-relative "
            f"API subpath with no leading slash or scheme (got {raw_path!r})",
            module_name,
        )
    if any(token in raw_path for token in ("?", "#", "<", ">", "\\")):
        raise ManifestError(
            f"frontend_resources.paths.{resource} must not carry a query "
            "string, fragment, angle-bracket route placeholder, or backslash "
            f"(got {raw_path!r})",
            module_name,
        )
    segments = raw_path.split("/")
    if segments and segments[-1] == "":
        segments = segments[:-1]
    if not segments:
        raise ManifestError(
            f"frontend_resources.paths.{resource} must name at least one "
            f"path segment (got {raw_path!r})",
            module_name,
        )
    for segment in segments:
        if segment in {".", ".."}:
            raise ManifestError(
                f"frontend_resources.paths.{resource} must not carry a '.' or "
                f"'..' segment (got {raw_path!r})",
                module_name,
            )
        if _FRONTEND_RESOURCE_SEGMENT.match(segment) is None:
            raise ManifestError(
                f"frontend_resources.paths.{resource} segments must be "
                "literal path segments or whole '{parameter}' placeholders "
                f"(got {raw_path!r})",
                module_name,
            )
    placeholders = _FRONTEND_RESOURCE_PLACEHOLDER.findall(raw_path)
    if len(placeholders) != len(set(placeholders)):
        raise ManifestError(
            f"frontend_resources.paths.{resource} must use each "
            f"'{{parameter}}' placeholder once (got {raw_path!r})",
            module_name,
        )
    reserved = sorted(set(placeholders) & _TS_RESERVED_PARAMETER_NAMES)
    if reserved:
        raise ManifestError(
            f"frontend_resources.paths.{resource} uses TypeScript reserved "
            f"word(s) as a builder parameter: {', '.join(reserved)} "
            f"(got {raw_path!r})",
            module_name,
        )
    return raw_path


def _parse_frontend_field_type(
    field_type: Any, field_name: str, module_name: str | None
) -> str:
    """Validate one payload field's TypeScript type expression."""
    if (
        not isinstance(field_type, str)
        or _FRONTEND_FIELD_TYPE.match(field_type) is None
    ):
        raise ManifestError(
            "frontend_resources.payload_types field "
            f"{field_name!r} must be a scalar (string, number, boolean), a "
            "declared type name, an array of either, or the same made "
            f"nullable with '| null' (got {field_type!r})",
            module_name,
        )
    return field_type


def _parse_frontend_payload_type(
    type_name: str, fields_raw: Any, module_name: str | None
) -> dict[str, str] | str:
    """Validate one ``frontend_resources.payload_types`` entry and return it."""
    if (
        not isinstance(type_name, str)
        or _FRONTEND_PAYLOAD_TYPE_NAME.match(type_name) is None
    ):
        raise ManifestError(
            "frontend_resources.payload_types keys must be type names "
            "(a capital letter followed by letters and digits)",
            module_name,
        )
    if isinstance(fields_raw, str):
        if _FRONTEND_UNION_TYPE.match(fields_raw) is None:
            raise ManifestError(
                f"frontend_resources.payload_types.{type_name} must be a "
                "field mapping or a union of two or more TypeScript atoms "
                f"(got {fields_raw!r})",
                module_name,
            )
        return fields_raw
    if not isinstance(fields_raw, dict) or not fields_raw:
        raise ManifestError(
            f"frontend_resources.payload_types.{type_name} must be a "
            "non-empty mapping of field name to type, or a union string",
            module_name,
        )
    fields: dict[str, str] = {}
    bare_names: set[str] = set()
    for field_name, field_type in fields_raw.items():
        if (
            not isinstance(field_name, str)
            or _FRONTEND_PAYLOAD_FIELD_NAME.match(field_name) is None
        ):
            raise ManifestError(
                f"frontend_resources.payload_types.{type_name} field names "
                "must be identifiers (letters, digits, and underscores, not "
                "starting with a digit), with a trailing '?' when optional",
                module_name,
            )
        bare_name = field_name[:-1] if field_name.endswith("?") else field_name
        if bare_name in bare_names:
            raise ManifestError(
                f"frontend_resources.payload_types.{type_name} declares field "
                f"{bare_name!r} more than once",
                module_name,
            )
        bare_names.add(bare_name)
        fields[field_name] = _parse_frontend_field_type(
            field_type, field_name, module_name
        )
    return fields


def _frontend_type_references(declaration: dict[str, str] | str) -> set[str]:
    """Return the payload type names one declaration references."""
    text = (
        declaration if isinstance(declaration, str) else " ".join(declaration.values())
    )
    # A quoted union member is a literal value, not a reference, even when it
    # starts with a capital letter.
    text = re.sub(r"'[^']*'", "", text)
    return set(_FRONTEND_TYPE_REFERENCE.findall(text))


def _validate_frontend_type_references(
    payload_types: dict[str, dict[str, str] | str], module_name: str | None
) -> None:
    """Refuse a payload type that references a type the module does not declare.

    The managed hook is one TypeScript namespace, but a module owns its own
    contract: a reference to another module's type would make that module's
    release a hidden dependency of this one.
    """
    declared = set(payload_types)
    for type_name, declaration in payload_types.items():
        missing = sorted(_frontend_type_references(declaration) - declared)
        if missing:
            raise ManifestError(
                "frontend_resources.payload_types."
                f"{type_name} references undeclared payload type(s): "
                f"{', '.join(missing)}",
                module_name,
            )


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

    An empty section, an unknown key, a malformed subpath, a payload field
    outside the supported TypeScript forms, or a reference to an undeclared
    payload type fails closed: an inert or silently ignored declaration would
    leave the user-owned file as the contract's real home.

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
    payload_types: dict[str, dict[str, str] | str] = {}
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

    _validate_frontend_type_references(payload_types, module_name)

    return FrontendResources(paths=paths, payload_types=payload_types)
