"""Initial migration for the QuickScale CRM module.

Collapsed SA92 migration: final-schema 0001 with all 7 CRM models
(Tag, Company, Contact, Stage, Deal, ContactNote, DealNote).

All tenant-scoped models inherit organization via TenantModel:
NOT NULL/PROTECT FK with all_objects as base manager.  Includes
owner-bucket uniqueness constraints, named (id, organization_id)
parent unique constraints, composite child FKs for org-equality
enforcement, FORCE RLS policies with NULLIF guard refresh, and
SET_NULL on created_by for SA35 account-deletion safety.

Named composite FKs (NOT DEFERRABLE):
  crm_contactnote_contact_org_fk CASCADE
  crm_dealnote_deal_org_fk CASCADE

Named parent unique constraints:
  crm_contact_id_org_unique
  crm_deal_id_org_unique
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

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
CRM_TAG_TABLE = "quickscale_modules_crm_tag"
CRM_COMPANY_TABLE = "quickscale_modules_crm_company"
CRM_CONTACT_TABLE = "quickscale_modules_crm_contact"
CRM_STAGE_TABLE = "quickscale_modules_crm_stage"
CRM_DEAL_TABLE = "quickscale_modules_crm_deal"
CRM_CONTACTNOTE_TABLE = "quickscale_modules_crm_contactnote"
CRM_DEALNOTE_TABLE = "quickscale_modules_crm_dealnote"

# ---------------------------------------------------------------------------
# RLS policy names
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Constraint names
# ---------------------------------------------------------------------------
CRM_CONTACT_ID_ORG_UNIQUE = "crm_contact_id_org_unique"
CRM_DEAL_ID_ORG_UNIQUE = "crm_deal_id_org_unique"
CRM_CONTACTNOTE_CONTACT_ORG_FK = "crm_contactnote_contact_org_fk"
CRM_DEALNOTE_DEAL_ORG_FK = "crm_dealnote_deal_org_fk"


def _forward_note_composite_fks_and_rls(apps: Any, schema_editor: Any) -> None:
    """Add composite child FKs (parent unique constraints already exist) and enable FORCE RLS."""
    del apps

    # Composite child FKs — NOT VALID then validate
    def _add_fk_not_valid(
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
            f"ON DELETE {on_delete} "
            f"NOT DEFERRABLE "
            f"NOT VALID"
        )

    def _validate_fk(
        child_table: str,
        constraint: str,
    ) -> None:
        schema_editor.execute(
            f"ALTER TABLE {child_table} VALIDATE CONSTRAINT {constraint}"
        )

    _add_fk_not_valid(
        child_table=CRM_CONTACTNOTE_TABLE,
        constraint=CRM_CONTACTNOTE_CONTACT_ORG_FK,
        child_fk_column="contact_id",
        parent_table=CRM_CONTACT_TABLE,
        on_delete="CASCADE",
    )
    _validate_fk(
        child_table=CRM_CONTACTNOTE_TABLE,
        constraint=CRM_CONTACTNOTE_CONTACT_ORG_FK,
    )
    _add_fk_not_valid(
        child_table=CRM_DEALNOTE_TABLE,
        constraint=CRM_DEALNOTE_DEAL_ORG_FK,
        child_fk_column="deal_id",
        parent_table=CRM_DEAL_TABLE,
        on_delete="CASCADE",
    )
    _validate_fk(
        child_table=CRM_DEALNOTE_TABLE,
        constraint=CRM_DEALNOTE_DEAL_ORG_FK,
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
    _all_targets = _CRM_CORE_RLS_TARGETS + _CRM_NOTE_RLS_TARGETS
    revert_force_rls(schema_editor, _all_targets)
    apply_force_rls(schema_editor, _all_targets)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---- Schema: Tag ----
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Schema: Company ----
        migrations.CreateModel(
            name="Company",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("industry", models.CharField(blank=True, max_length=100)),
                ("website", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Companies",
                "ordering": ["name"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Schema: Stage ----
        migrations.CreateModel(
            name="Stage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
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
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "name"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Schema: Contact ----
        migrations.CreateModel(
            name="Contact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
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
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="quickscale_modules_crm.company",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="contacts",
                        to="quickscale_modules_crm.tag",
                    ),
                ),
            ],
            options={
                "ordering": ["last_name", "first_name"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Schema: Deal ----
        migrations.CreateModel(
            name="Deal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
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
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deals",
                        to="quickscale_modules_crm.contact",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_deals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="deals",
                        to="quickscale_modules_crm.stage",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="deals",
                        to="quickscale_modules_crm.tag",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Schema: ContactNote ----
        migrations.CreateModel(
            name="ContactNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quickscale_modules_crm.contact",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Schema: DealNote ----
        migrations.CreateModel(
            name="DealNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "deal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quickscale_modules_crm.deal",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # ---- Tag constraints: owner-bucket uniqueness ----
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                fields=("name",),
                name="crm_tag_name_unique_null_org",
                condition=Q(organization__isnull=True),
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                fields=("name", "organization"),
                name="crm_tag_name_organization_unique",
                condition=Q(organization__isnull=False),
            ),
        ),
        # ---- Stage constraints: owner-bucket terminal_semantic uniqueness ----
        migrations.AddConstraint(
            model_name="stage",
            constraint=models.UniqueConstraint(
                fields=("terminal_semantic",),
                name="crm_stage_terminal_semantic_unique_null_org",
                condition=Q(organization__isnull=True),
            ),
        ),
        migrations.AddConstraint(
            model_name="stage",
            constraint=models.UniqueConstraint(
                fields=("terminal_semantic", "organization"),
                name="crm_stage_terminal_semantic_organization_unique",
                condition=Q(organization__isnull=False),
            ),
        ),
        # ---- Contact parent unique constraint ----
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"),
                name="crm_contact_id_org_unique",
            ),
        ),
        # ---- Deal parent unique constraint ----
        migrations.AddConstraint(
            model_name="deal",
            constraint=models.UniqueConstraint(
                fields=("id", "organization"),
                name="crm_deal_id_org_unique",
            ),
        ),
        # ---- Step 1: Add composite child FKs for note tables ----
        migrations.RunPython(
            code=_forward_note_composite_fks_and_rls,
            reverse_code=_reverse_note_composite_fks_and_rls,
            hints={"target_db": "default"},
        ),
        # ---- Step 2: Install FORCE RLS on all CRM tables with current NULLIF-guarded template ----
        migrations.RunPython(
            code=_forward_refresh_rls_nullif,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
