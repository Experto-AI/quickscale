"""Cross-row tenant-reference equality discovery and inspection.

Every foreign key between two tenant models must carry a composite
``(fk_column, organization_id)`` constraint referencing the parent's
``(target_column, organization_id)`` pair, so PostgreSQL itself rejects a child
row that points at another organization's row.  A model may instead record
a reasoned ``tenant_reference_exemptions`` entry per reference.

The reference set is derived from model metadata — never hand-listed — so a
project-owned foreign key is covered without editing vendored module source.
The conformance tests derive their expectations from
:func:`get_tenant_references`, and ``checks.py`` registers the warning built
on :func:`tenant_reference_equality_gaps`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from django.db import connection, models

from quickscale_modules_orgs._tenancy_discovery import ORG_ID_COLUMN, get_tenant_models

#: Model attribute recording per-field exemptions from the composite
#: constraint contract: a field-name-to-reason mapping on the child model.
TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE: str = "tenant_reference_exemptions"

_COMPOSITE_REFERENCE_SQL = """
SELECT
    pc.conname,
    child_cols.names,
    parent_cols.names,
    pc.condeferrable
FROM pg_catalog.pg_constraint AS pc
JOIN pg_catalog.pg_class AS child ON child.oid = pc.conrelid
JOIN pg_catalog.pg_class AS parent ON parent.oid = pc.confrelid
JOIN pg_catalog.pg_namespace AS child_ns ON child_ns.oid = child.relnamespace
JOIN pg_catalog.pg_namespace AS parent_ns ON parent_ns.oid = parent.relnamespace
CROSS JOIN LATERAL (
    SELECT array_agg(
        a.attname::text ORDER BY array_position(pc.conkey, a.attnum)
    ) AS names
    FROM unnest(pc.conkey) AS key_column(attnum)
    JOIN pg_catalog.pg_attribute AS a
      ON a.attrelid = pc.conrelid AND a.attnum = key_column.attnum
) AS child_cols
CROSS JOIN LATERAL (
    SELECT array_agg(
        a.attname::text ORDER BY array_position(pc.confkey, a.attnum)
    ) AS names
    FROM unnest(pc.confkey) AS key_column(attnum)
    JOIN pg_catalog.pg_attribute AS a
      ON a.attrelid = pc.confrelid AND a.attnum = key_column.attnum
) AS parent_cols
WHERE pc.contype = 'f'
  AND child_ns.nspname = current_schema()
  AND parent_ns.nspname = current_schema()
  AND child.relname = %s
  AND parent.relname = %s
"""


@dataclass(frozen=True)
class TenantReference:
    """One foreign key from a tenant model to another tenant model."""

    model_label: str
    field_name: str
    child_table: str
    fk_column: str
    parent_label: str
    parent_table: str
    parent_target_column: str
    exempt_reason: str | None


@dataclass(frozen=True)
class CompositeReferenceConstraint:
    """A PostgreSQL composite foreign key backing one tenant reference."""

    constraint_name: str
    deferrable: bool


def _tenant_reference_exemptions(model: type[models.Model]) -> dict[str, str]:
    """Return *model*'s validated ``tenant_reference_exemptions`` mapping.

    Raises:
        ValueError: when the declaration is not a field-name-to-reason
            mapping carrying a non-empty reason per entry.  Callers fail
            closed rather than treat an unreadable declaration as "no
            exemptions".
    """
    declaration = getattr(model, TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE, None)
    if declaration is None:
        return {}
    if not isinstance(declaration, Mapping):
        raise ValueError(
            f"{model._meta.label_lower} declares a non-mapping "
            f"{TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE}; expected a "
            "field-name-to-reason mapping."
        )
    validated: dict[str, str] = {}
    for field_name, reason in declaration.items():
        if not isinstance(field_name, str) or not field_name:
            raise ValueError(
                f"{model._meta.label_lower} declares a "
                f"{TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE} entry with a "
                "non-string field name."
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                f"{model._meta.label_lower} declares a "
                f"{TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE} entry for "
                f"{field_name!r} without a non-empty reason."
            )
        validated[field_name] = reason
    return validated


def get_tenant_references(
    tenant_models: Iterable[type[models.Model]] | None = None,
) -> tuple[TenantReference, ...]:
    """Derive every tenant-to-tenant foreign key from model metadata.

    Walks the marker-derived tenant models and returns one record per
    concrete single-column foreign key whose target is another tenant
    model: a proxy target resolves through Django's ``concrete_model``, and
    the referenced parent column is the relation's own target field (the
    parent's primary key unless the relation declares ``to_field``).  The
    reference's composite constraint exemption (if any) is resolved from the
    child model's declaration.

    Multi-table-inheritance parent links are not references: a child table
    stores no local ``organization_id`` column for them.

    Raises:
        ValueError: when a model's ``tenant_reference_exemptions``
            declaration is unreadable.
    """
    if tenant_models is None:
        tenant_models = get_tenant_models()
    candidates = list(tenant_models)
    tenant_set = set(candidates)
    references: list[TenantReference] = []
    for model in candidates:
        exemptions = _tenant_reference_exemptions(model)
        for field in model._meta.get_fields():
            if not isinstance(field, models.ForeignKey):
                continue
            if (
                field.auto_created
                or not field.concrete
                or field.remote_field.parent_link
            ):
                continue
            related_model = field.related_model
            concrete_parent = related_model._meta.concrete_model
            if concrete_parent not in tenant_set:
                continue
            target_column = field.target_field.column
            if target_column is None:
                continue
            references.append(
                TenantReference(
                    model_label=model._meta.label_lower,
                    field_name=field.name,
                    child_table=model._meta.db_table,
                    fk_column=field.column,
                    parent_label=concrete_parent._meta.label_lower,
                    parent_table=concrete_parent._meta.db_table,
                    parent_target_column=target_column,
                    exempt_reason=exemptions.get(field.name),
                )
            )
    references.sort(key=lambda reference: (reference.model_label, reference.field_name))
    return tuple(references)


def find_composite_reference_constraint(
    reference: TenantReference,
) -> CompositeReferenceConstraint | None:
    """Return the composite constraint backing *reference*, if any.

    The lookup is name-independent: it accepts only a two-column foreign key
    whose declared pairs map the child's ``fk_column`` to the parent's target
    column and the child's ``organization_id`` to the parent's
    ``organization_id`` in the current schema.  A wider composite with an
    extra nullable key column cannot guarantee the equality under MATCH
    SIMPLE, so it is not accepted.  Returns ``None`` on non-PostgreSQL
    databases and when no such constraint exists (including a not-yet-migrated
    table).
    """
    if connection.vendor != "postgresql":
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            _COMPOSITE_REFERENCE_SQL,
            [reference.child_table, reference.parent_table],
        )
        rows = cursor.fetchall()
    for constraint_name, child_columns, parent_columns, deferrable in rows:
        pairing = dict(zip(child_columns, parent_columns))
        if (
            len(pairing) == 2
            and pairing.get(reference.fk_column) == reference.parent_target_column
            and pairing.get(ORG_ID_COLUMN) == ORG_ID_COLUMN
        ):
            return CompositeReferenceConstraint(
                constraint_name=constraint_name,
                deferrable=bool(deferrable),
            )
    return None


def tenant_reference_equality_gaps(
    tenant_models: Iterable[type[models.Model]] | None = None,
) -> tuple[str, ...]:
    """Return one message per tenant reference without storage equality.

    Reports a reference whose composite constraint is absent and that no
    ``tenant_reference_exemptions`` entry covers, an unreadable declaration,
    and an exemption that names no tenant-to-tenant foreign key.  The
    catalog is read only on PostgreSQL databases.
    """
    if tenant_models is None:
        tenant_models = get_tenant_models()
    candidates = list(tenant_models)
    try:
        references = get_tenant_references(candidates)
    except ValueError as exc:
        return (str(exc),)

    gaps: list[str] = []
    reference_fields: dict[str, set[str]] = {}
    for reference in references:
        reference_fields.setdefault(reference.model_label, set()).add(
            reference.field_name
        )
    for model in candidates:
        declaration = getattr(model, TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE, None)
        if declaration is None:
            continue
        model_label = model._meta.label_lower
        declared_fields = reference_fields.get(model_label, set())
        for field_name in declaration:
            if field_name not in declared_fields:
                gaps.append(
                    f"{model_label} declares a "
                    f"{TENANT_REFERENCE_EXEMPTIONS_ATTRIBUTE} entry for "
                    f"{field_name!r}, which is not a foreign key to another "
                    "tenant model"
                )

    if connection.vendor != "postgresql":
        return tuple(gaps)

    for reference in references:
        if reference.exempt_reason is not None:
            continue
        if find_composite_reference_constraint(reference) is None:
            gaps.append(
                f"{reference.model_label}.{reference.field_name} references "
                f"{reference.parent_label} without a composite "
                f"({reference.fk_column}, {ORG_ID_COLUMN}) constraint to "
                f"{reference.parent_table}({reference.parent_target_column}, "
                f"{ORG_ID_COLUMN})"
            )
    return tuple(gaps)
