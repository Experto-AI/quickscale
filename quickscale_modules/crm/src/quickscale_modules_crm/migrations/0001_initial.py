"""Initial migration for the QuickScale CRM module.

Collapsed SA92 migration: final-schema 0001 with all 7 CRM models.  The
private constructors below only remove repetition from the generated schema;
the historical operations, callable identities, SQL, and payloads remain
unchanged.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

from quickscale_modules_orgs.tenancy import (
    apply_force_rls,
    remove_composite_child_fk,
    revert_force_rls,
)

CRM_TAG_TABLE = "quickscale_modules_crm_tag"
CRM_COMPANY_TABLE = "quickscale_modules_crm_company"
CRM_CONTACT_TABLE = "quickscale_modules_crm_contact"
CRM_STAGE_TABLE = "quickscale_modules_crm_stage"
CRM_DEAL_TABLE = "quickscale_modules_crm_deal"
CRM_CONTACTNOTE_TABLE = "quickscale_modules_crm_contactnote"
CRM_DEALNOTE_TABLE = "quickscale_modules_crm_dealnote"

CRM_TAG_RLS_POLICY = "crm_tag_org_isolation"
CRM_COMPANY_RLS_POLICY = "crm_company_org_isolation"
CRM_CONTACT_RLS_POLICY = "crm_contact_org_isolation"
CRM_STAGE_RLS_POLICY = "crm_stage_org_isolation"
CRM_DEAL_RLS_POLICY = "crm_deal_org_isolation"
CRM_CONTACTNOTE_RLS_POLICY = "crm_contactnote_org_isolation"
CRM_DEALNOTE_RLS_POLICY = "crm_dealnote_org_isolation"

_CRM_CORE_RLS_TARGETS = (
    (CRM_TAG_TABLE, CRM_TAG_RLS_POLICY),
    (CRM_COMPANY_TABLE, CRM_COMPANY_RLS_POLICY),
    (CRM_CONTACT_TABLE, CRM_CONTACT_RLS_POLICY),
    (CRM_STAGE_TABLE, CRM_STAGE_RLS_POLICY),
    (CRM_DEAL_TABLE, CRM_DEAL_RLS_POLICY),
)
_CRM_NOTE_RLS_TARGETS = (
    (CRM_CONTACTNOTE_TABLE, CRM_CONTACTNOTE_RLS_POLICY),
    (CRM_DEALNOTE_TABLE, CRM_DEALNOTE_RLS_POLICY),
)

CRM_CONTACT_ID_ORG_UNIQUE = "crm_contact_id_org_unique"
CRM_DEAL_ID_ORG_UNIQUE = "crm_deal_id_org_unique"
CRM_CONTACTNOTE_CONTACT_ORG_FK = "crm_contactnote_contact_org_fk"
CRM_DEALNOTE_DEAL_ORG_FK = "crm_dealnote_deal_org_fk"


def _id() -> tuple[str, Any]:
    return "id", models.BigAutoField(
        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
    )


def _org() -> tuple[str, Any]:
    return "organization", models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
        to="quickscale_modules_orgs.organization",
    )


def _fk(to: str, on_delete: Any, **kwargs: Any) -> Any:
    return models.ForeignKey(on_delete=on_delete, to=to, **kwargs)


def _model(
    name: str, fields: list[tuple[str, Any]], ordering: list[str], **options: Any
) -> migrations.CreateModel:
    return migrations.CreateModel(
        name=name,
        fields=[_id(), *fields],
        options={"ordering": ordering, "base_manager_name": "all_objects", **options},
        managers=[
            ("objects", django.db.models.manager.Manager()),
            ("all_objects", django.db.models.manager.Manager()),
        ],
    )


def _unique(
    model_name: str, fields: tuple[str, ...], name: str, **kwargs: Any
) -> migrations.AddConstraint:
    return migrations.AddConstraint(
        model_name=model_name,
        constraint=models.UniqueConstraint(fields=fields, name=name, **kwargs),
    )


def _add_composite_fk(
    schema_editor: Any,
    child_table: str,
    constraint: str,
    child_fk_column: str,
    parent_table: str,
    on_delete: str,
) -> None:
    schema_editor.execute(
        f"ALTER TABLE {child_table} ADD CONSTRAINT {constraint} "
        f"FOREIGN KEY ({child_fk_column}, organization_id) "
        f"REFERENCES {parent_table}(id, organization_id) "
        f"ON DELETE {on_delete} NOT DEFERRABLE NOT VALID"
    )
    schema_editor.execute(f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {constraint}")


def _forward_note_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add composite child FKs (parent unique constraints already exist) and enable FORCE RLS."""
    del apps
    _add_composite_fk(
        schema_editor,
        CRM_CONTACTNOTE_TABLE,
        CRM_CONTACTNOTE_CONTACT_ORG_FK,
        "contact_id",
        CRM_CONTACT_TABLE,
        "CASCADE",
    )
    _add_composite_fk(
        schema_editor,
        CRM_DEALNOTE_TABLE,
        CRM_DEALNOTE_DEAL_ORG_FK,
        "deal_id",
        CRM_DEAL_TABLE,
        "CASCADE",
    )


def _reverse_note_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Reverse: drop composite FKs (RLS managed separately)."""
    del apps
    remove_composite_child_fk(
        schema_editor,
        child_table=CRM_CONTACTNOTE_TABLE,
        constraint_name=CRM_CONTACTNOTE_CONTACT_ORG_FK,
    )
    remove_composite_child_fk(
        schema_editor,
        child_table=CRM_DEALNOTE_TABLE,
        constraint_name=CRM_DEALNOTE_DEAL_ORG_FK,
    )


def _forward_refresh_rls_nullif(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the NULLIF-guarded template."""
    del apps
    targets = _CRM_CORE_RLS_TARGETS + _CRM_NOTE_RLS_TARGETS
    revert_force_rls(schema_editor, targets)
    apply_force_rls(schema_editor, targets)


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        _model(
            "Tag",
            [
                ("name", models.CharField(max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                _org(),
            ],
            ["name"],
        ),
        _model(
            "Company",
            [
                ("name", models.CharField(max_length=200)),
                ("industry", models.CharField(blank=True, max_length=100)),
                ("website", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                _org(),
            ],
            ["name"],
            verbose_name_plural="Companies",
        ),
        _model(
            "Stage",
            [
                ("name", models.CharField(max_length=100)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "terminal_semantic",
                    models.CharField(
                        blank=True,
                        choices=[("won", "Won"), ("lost", "Lost")],
                        editable=False,
                        max_length=20,
                        null=True,
                    ),
                ),
                _org(),
            ],
            ["order", "name"],
        ),
        _model(
            "Contact",
            [
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=20)),
                (
                    "title",
                    models.CharField(blank=True, help_text="Job title", max_length=100),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("in_discussion", "In Discussion"),
                            ("pending_response", "Pending Response"),
                            ("inactive", "Inactive"),
                        ],
                        default="new",
                        max_length=50,
                    ),
                ),
                (
                    "last_contacted_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Automatically updated when a note is logged",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    _fk(
                        "quickscale_modules_crm.company",
                        django.db.models.deletion.CASCADE,
                        related_name="contacts",
                    ),
                ),
                _org(),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="contacts",
                        to="quickscale_modules_crm.tag",
                    ),
                ),
            ],
            ["last_name", "first_name"],
        ),
        _model(
            "Deal",
            [
                ("title", models.CharField(max_length=200)),
                (
                    "amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Deal value in USD",
                        max_digits=12,
                        null=True,
                    ),
                ),
                ("expected_close_date", models.DateField(blank=True, null=True)),
                (
                    "probability",
                    models.IntegerField(
                        default=50, help_text="Forecast likelihood (0-100%)"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contact",
                    _fk(
                        "quickscale_modules_crm.contact",
                        django.db.models.deletion.CASCADE,
                        related_name="deals",
                    ),
                ),
                (
                    "owner",
                    _fk(
                        settings.AUTH_USER_MODEL,
                        django.db.models.deletion.SET_NULL,
                        blank=True,
                        null=True,
                        related_name="owned_deals",
                    ),
                ),
                (
                    "stage",
                    _fk(
                        "quickscale_modules_crm.stage",
                        django.db.models.deletion.PROTECT,
                        related_name="deals",
                    ),
                ),
                _org(),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="deals",
                        to="quickscale_modules_crm.tag",
                    ),
                ),
            ],
            ["-created_at"],
        ),
        _model(
            "ContactNote",
            [
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contact",
                    _fk(
                        "quickscale_modules_crm.contact",
                        django.db.models.deletion.CASCADE,
                        related_name="notes",
                    ),
                ),
                (
                    "created_by",
                    _fk(
                        settings.AUTH_USER_MODEL,
                        django.db.models.deletion.SET_NULL,
                        blank=True,
                        null=True,
                    ),
                ),
                _org(),
            ],
            ["-created_at"],
        ),
        _model(
            "DealNote",
            [
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    _fk(
                        settings.AUTH_USER_MODEL,
                        django.db.models.deletion.SET_NULL,
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "deal",
                    _fk(
                        "quickscale_modules_crm.deal",
                        django.db.models.deletion.CASCADE,
                        related_name="notes",
                    ),
                ),
                _org(),
            ],
            ["-created_at"],
        ),
        _unique(
            "tag",
            ("name",),
            "crm_tag_name_unique_null_org",
            condition=Q(organization__isnull=True),
        ),
        _unique(
            "tag",
            ("name", "organization"),
            "crm_tag_name_organization_unique",
            condition=Q(organization__isnull=False),
        ),
        _unique(
            "stage",
            ("terminal_semantic",),
            "crm_stage_terminal_semantic_unique_null_org",
            condition=Q(organization__isnull=True),
        ),
        _unique(
            "stage",
            ("terminal_semantic", "organization"),
            "crm_stage_terminal_semantic_organization_unique",
            condition=Q(organization__isnull=False),
        ),
        _unique("contact", ("id", "organization"), CRM_CONTACT_ID_ORG_UNIQUE),
        _unique("deal", ("id", "organization"), CRM_DEAL_ID_ORG_UNIQUE),
        migrations.RunPython(
            code=_forward_note_composite_fks_and_rls,
            reverse_code=_reverse_note_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
        migrations.RunPython(
            code=_forward_refresh_rls_nullif,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
