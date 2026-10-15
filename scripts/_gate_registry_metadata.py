#!/usr/bin/env python3
"""
Private sibling: the per-gate metadata validators for the gate registry (SA278b).

``_gate_registry_schema`` imports these names for its per-gate validators, so
the ``check_gate_parity`` facade's pre-split surface is unchanged; the
validators live in this module so the schema module stays inside the file-size
threshold.  The structured error, the strict-int check, the registry index, and
the echo-safe character set travel with the validators as the vocabulary they
share.  Diagnostic messages, field paths, and the order in which the first
violation is reported are the pre-split contract and are pinned by the parity
controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_REGEN_CHARS = ('"', "\\", "$", "`")

_HOSTED_METADATA_KEYS: frozenset[str] = frozenset(
    {"order", "display_name", "check_step_name", "full_history"}
)

_PUBLISH_METADATA_KEYS: frozenset[str] = frozenset({"order", "step_name", "command_prefix"})

_LOCAL_METADATA_KEYS: frozenset[str] = frozenset(
    {"order", "description", "success", "failure_label"}
)

_MAKEFILE_HELP_METADATA_KEYS: frozenset[str] = frozenset({"order", "text"})


class SchemaValidationError(ValueError):
    """Structured validation error with source label and field path."""

    def __init__(self, source: str, path: str, message: str) -> None:
        self.source = source
        self.path = path
        self.message = message
        super().__init__(message)


def _is_strict_int(value: object) -> bool:
    """Return True if *value* is an ``int`` but not a ``bool``."""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass
class _RegistryIndex:
    """Per-registry bookkeeping shared across the per-gate validators."""

    seen_ids: set[str] = field(default_factory=set)
    seen_make_targets: dict[str, str] = field(default_factory=dict)
    seen_ci_jobs: dict[str, str] = field(default_factory=dict)
    seen_hosted_orders: dict[int, str] = field(default_factory=dict)
    seen_publish_orders: dict[int, str] = field(default_factory=dict)
    seen_local_orders: dict[int, str] = field(default_factory=dict)
    seen_makefile_help_orders: dict[int, str] = field(default_factory=dict)


def _require_metadata_mapping(
    gate: dict[str, Any],
    i: int,
    gid: str,
    key: str,
    allowed: frozenset[str],
    *,
    required: tuple[str, ...],
) -> dict[str, Any]:
    """Validate one per-gate metadata object's shape and required keys."""
    metadata = gate.get(key)
    if not isinstance(metadata, dict):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{key}",
            f"gate[{i}] ({gid}).{key} must be a dict",
        )
    unknown = set(metadata.keys()) - allowed
    if unknown:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{key}",
            f"gate[{i}] ({gid}).{key} contains unknown key(s): {', '.join(sorted(unknown))}",
        )
    missing = [name for name in required if name not in metadata]
    if missing:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{key}",
            f"gate[{i}] ({gid}).{key} is missing required key(s): {', '.join(missing)}",
        )
    return metadata


def _require_single_line_text(value: Any, i: int, gid: str, path: str, label: str) -> None:
    """Require one non-empty, newline-free string emitted into generated text."""
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must be a non-empty string",
        )
    if "\n" in value or "\r" in value:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must be a single line",
        )


def _require_positive_order(value: Any, i: int, gid: str, path: str, label: str) -> int:
    """Require a strict positive integer order for one generated station."""
    if not _is_strict_int(value) or value < 1:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must be a positive integer",
        )
    return value


def _validate_hosted_metadata(
    gate: dict[str, Any], i: int, gid: str, rc: list[str], index: _RegistryIndex
) -> None:
    """
    Validate the hosted presentation metadata and its context pairing.

    A hosted-context gate must carry the display name, check-step label, and
    execution order the generator projects into ``ci.yml``; metadata without
    the declared context, and a ``ci_job`` binding no hosted projection would
    consume, fail closed too.  Every field is optional only by absence: a
    present ``hosted``/``full_history`` value must be valid, so JSON null
    cannot silently stand in for omission.
    """
    hosted_declared = "hosted" in rc
    ci_job = gate["bindings"].get("ci_job")
    if ci_job is not None and not hosted_declared:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].bindings.ci_job",
            f"gate[{i}] ({gid}).bindings.ci_job requires the hosted context",
        )
    if "hosted" not in gate:
        if hosted_declared:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].hosted",
                f"gate[{i}] ({gid}).hosted is required when the hosted context is declared",
            )
        return
    metadata = _require_metadata_mapping(
        gate,
        i,
        gid,
        "hosted",
        _HOSTED_METADATA_KEYS,
        required=("order", "display_name", "check_step_name"),
    )
    if not hosted_declared:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].hosted",
            f"gate[{i}] ({gid}).hosted metadata requires the hosted context",
        )
    order = _require_positive_order(metadata["order"], i, gid, "hosted.order", "hosted.order")
    _require_single_line_text(
        metadata["display_name"], i, gid, "hosted.display_name", "hosted.display_name"
    )
    _require_single_line_text(
        metadata["check_step_name"], i, gid, "hosted.check_step_name", "hosted.check_step_name"
    )
    if "full_history" in metadata and not isinstance(metadata["full_history"], bool):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].hosted.full_history",
            f"gate[{i}] ({gid}).hosted.full_history must be a boolean",
        )
    if order in index.seen_hosted_orders:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].hosted.order",
            f"hosted order {order} already used by gate {index.seen_hosted_orders[order]!r}",
        )
    index.seen_hosted_orders[order] = gid


def _validate_publish_metadata(
    gate: dict[str, Any], i: int, gid: str, rc: list[str], index: _RegistryIndex
) -> None:
    """Validate the publish step metadata and its context pairing."""
    publish_declared = "publish" in rc
    if "publish" not in gate:
        if publish_declared:
            raise SchemaValidationError(
                "registry",
                f"gates[{i}].publish",
                f"gate[{i}] ({gid}).publish is required when the publish context is declared",
            )
        return
    metadata = _require_metadata_mapping(
        gate,
        i,
        gid,
        "publish",
        _PUBLISH_METADATA_KEYS,
        required=("order", "step_name"),
    )
    if not publish_declared:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].publish",
            f"gate[{i}] ({gid}).publish metadata requires the publish context",
        )
    order = _require_positive_order(metadata["order"], i, gid, "publish.order", "publish.order")
    _require_single_line_text(
        metadata["step_name"], i, gid, "publish.step_name", "publish.step_name"
    )
    if "command_prefix" in metadata:
        _require_single_line_text(
            metadata["command_prefix"], i, gid, "publish.command_prefix", "publish.command_prefix"
        )
    if order in index.seen_publish_orders:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].publish.order",
            f"publish order {order} already used by gate {index.seen_publish_orders[order]!r}",
        )
    index.seen_publish_orders[order] = gid


def _validate_help_metadata(gate: dict[str, Any], i: int, gid: str) -> None:
    """Validate the optional curated Make-target comment (absent, or non-empty)."""
    if "help" not in gate:
        return
    help_text = gate["help"]
    if (
        not isinstance(help_text, str)
        or not help_text.strip()
        or help_text != help_text.rstrip()
        or "\r" in help_text
    ):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].help",
            f"gate[{i}] ({gid}).help must be a non-empty trimmed string",
        )


def _require_echo_safe_text(value: Any, i: int, gid: str, path: str, label: str) -> None:
    """
    Require one literal line emitted inside generated double-quoted shell text.

    A local-CI arm assignment or a Makefile help line is emitted verbatim, so a
    double quote, backslash, dollar sign, or backtick would change the generated
    file's meaning; fail closed instead of escaping registry-owned text.
    """
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must be a non-empty string",
        )
    if "\n" in value or "\r" in value:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must be a single line",
        )
    if value != value.strip():
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must be one whitespace-trimmed line",
        )
    if any(character in value for character in _REGEN_CHARS):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].{path}",
            f"gate[{i}] ({gid}).{label} must not contain a double quote, backslash, "
            "dollar sign, or backtick",
        )


def _validate_local_metadata(gate: dict[str, Any], i: int, gid: str, index: _RegistryIndex) -> None:
    """
    Validate the optional local-CI display metadata and its unique order.

    The local runner's display arms key on the Make target, so metadata without
    one would never be projected and fails closed instead.  A gate without the
    metadata keeps the runner's generic fallback text.
    """
    if "local" not in gate:
        return
    metadata = _require_metadata_mapping(
        gate,
        i,
        gid,
        "local",
        _LOCAL_METADATA_KEYS,
        required=("order", "description", "success", "failure_label"),
    )
    if not isinstance(gate["bindings"].get("make_target"), str):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].local",
            f"gate[{i}] ({gid}).local requires a string make_target binding",
        )
    order = _require_positive_order(metadata["order"], i, gid, "local.order", "local.order")
    for key in ("description", "success", "failure_label"):
        _require_echo_safe_text(metadata[key], i, gid, f"local.{key}", f"local.{key}")
    if order in index.seen_local_orders:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].local.order",
            f"local order {order} already used by gate {index.seen_local_orders[order]!r}",
        )
    index.seen_local_orders[order] = gid


def _validate_makefile_help_metadata(
    gate: dict[str, Any], i: int, gid: str, index: _RegistryIndex
) -> None:
    """
    Validate the optional Makefile help line and its unique order.

    The line is emitted verbatim inside the generated help block, so it must
    name the gate's own Make target; a gate without the metadata keeps its help
    line hand-written outside the generated region.
    """
    if "makefile_help" not in gate:
        return
    metadata = _require_metadata_mapping(
        gate,
        i,
        gid,
        "makefile_help",
        _MAKEFILE_HELP_METADATA_KEYS,
        required=("order", "text"),
    )
    target = gate["bindings"].get("make_target")
    if not isinstance(target, str):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].makefile_help",
            f"gate[{i}] ({gid}).makefile_help requires a string make_target binding",
        )
    order = _require_positive_order(
        metadata["order"], i, gid, "makefile_help.order", "makefile_help.order"
    )
    _require_echo_safe_text(metadata["text"], i, gid, "makefile_help.text", "makefile_help.text")
    if not metadata["text"].startswith(f"make {target} "):
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].makefile_help.text",
            f"gate[{i}] ({gid}).makefile_help.text must name its own Make target {target!r}",
        )
    if order in index.seen_makefile_help_orders:
        raise SchemaValidationError(
            "registry",
            f"gates[{i}].makefile_help.order",
            f"makefile help order {order} already used by gate "
            f"{index.seen_makefile_help_orders[order]!r}",
        )
    index.seen_makefile_help_orders[order] = gid
