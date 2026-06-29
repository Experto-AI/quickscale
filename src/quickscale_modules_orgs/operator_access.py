"""Operator-access seam for explicit cross-tenant or super-scope operations.

AF3 formalises the operator path — any code that must bypass the default
tenant-scoped manager (``TenantManager``) should do so through a single
``operator_access()`` context manager that emits structured audit records.

The audit trail uses Python logging (INFO-level structured log events)
rather than a database table.  Stable audit fields are preserved for
compliance, debugging, and deterministic failure-path testing.

Usage::

    from quickscale_modules_orgs.operator_access import operator_access

    with operator_access(reason="Purging expired org") as record:
        record.command = "purge_organization"
        record.actor_identifier = "system"
        record.target_scope = "single_org"
        record.target_org_ids = [str(org_id)]
        record.touched_org_ids = [str(org_id)]
        # … destructive operations …
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class OperatorAccessRecord:
    """In-memory audit record populated by the caller and emitted on close.

    Stable audit fields required by the AF3 contract:
    ``command``, ``reason``, ``actor_identifier``, ``target_scope``,
    ``target_org_ids``, ``touched_org_ids``, ``status``, ``error_class``.
    """

    command: str = ""
    reason: str = ""
    actor_identifier: str = ""
    target_scope: str = ""
    target_org_ids: list[str] = field(default_factory=list)
    touched_org_ids: list[str] = field(default_factory=list)
    status: str = "started"
    error_class: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


def _format_org_ids(ids: list[str]) -> str:
    """Format a list of org IDs for the log message."""
    if not ids:
        return ""
    return ",".join(ids)


@contextmanager
def operator_access(*, reason: str) -> Iterator[OperatorAccessRecord]:
    """Context manager for operator-level access with a structured audit trail.

    Parameters
    ----------
    reason : str
        Human-readable explanation of why operator-level access is needed.

    Yields
    ------
    OperatorAccessRecord
        An in-memory record that the caller **must** populate with
        ``command``, ``actor_identifier``, ``target_scope``,
        ``target_org_ids``, and ``touched_org_ids`` before performing the
        operation.

    On success the audit record's ``status`` is set to ``"succeeded"``;
    on any exception it is set to ``"failed"`` and ``error_class`` captures
    the exception type name.  The exception is re-raised after logging.
    """
    now = timezone.now()
    record = OperatorAccessRecord(
        reason=reason,
        status="started",
        started_at=now,
    )
    try:
        yield record
        record.status = "succeeded"
    except BaseException as exc:
        record.status = "failed"
        record.error_class = type(exc).__name__
        raise
    finally:
        record.completed_at = timezone.now()
        logger.info(
            "operator_access: status=%s command=%s scope=%s reason=%s "
            "actor=%s target_orgs=%s touched_orgs=%s error_class=%s",
            record.status,
            record.command,
            record.target_scope,
            record.reason,
            record.actor_identifier,
            _format_org_ids(record.target_org_ids),
            _format_org_ids(record.touched_org_ids),
            record.error_class,
        )


def operator_queryset(model: object) -> object:
    """Return an unfiltered queryset for operator-level access.

    Intended for use inside an ``operator_access()`` context so that
    management commands do not reference ``model.all_objects`` directly.
    Every direct ``.all_objects.`` reference in management command files
    should be replaced with ``operator_queryset(model)``.

    Example::

        from quickscale_modules_orgs.operator_access import (
            operator_access,
            operator_queryset,
        )

        with operator_access(reason="…") as _:
            rows = operator_queryset(MyModel).filter(...)
    """
    return model.all_objects  # type: ignore[union-attr]
