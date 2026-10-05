"""Personal-data declarations and coverage for account anonymization (rule 49).

Every module declares the treatment of its own user-linked fields beside its
anonymization handler, on its ``AppConfig`` through the
``personal_data_declarations`` capability; :func:`declared_personal_data`
collects them with :func:`quickscale_core.runtime.collect_capabilities` and adds
the rows no installed module declares for itself — orgs' own rows and the
contrib/third-party rows (Django admin, sessions, allauth's account).

:func:`candidate_kinds` and :func:`walk_candidate_fields` classify a model
field that could hold personal data.  :func:`personal_data_coverage_gaps` walks
the project-owned models and reports every candidate that is neither declared
with a treatment nor excluded with a reason, and
``checks.check_personal_data_declarations`` (``quickscale_orgs.W006``) reports
the same gaps as warnings at runtime, where a project app's own models are
installed.  The closed-world test in ``tests/test_personal_data_inventory.py``
runs the same helpers over the shipped models.

A candidate field is:

* a relation targeting ``AUTH_USER_MODEL``;
* an ``EmailField``;
* a ``GenericIPAddressField``;
* a file field (``FileField`` / ``ImageField``); or
* a ``TextField`` on a model that references the user.

Analytics (PostHog) events keyed by the user's ``distinct_id`` live outside the
database and are the operator's deletion step; no installed model field records
them.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models.fields.reverse_related import ForeignObjectRel

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
    collect_capabilities,
)

#: The ``AppConfig`` capability a module declares its personal-data rows with.
PERSONAL_DATA_DECLARATIONS_CAPABILITY = "personal_data_declarations"


class CandidateKind(enum.Enum):
    """A candidate rule that flags a field for classification."""

    USER_REFERENCE = "user reference"
    EMAIL = "email"
    IP_ADDRESS = "ip address"
    FILE = "file"
    FREE_TEXT = "free text"


@dataclass(frozen=True)
class CandidateField:
    """A field flagged by at least one candidate rule."""

    app_label: str
    model_name: str
    field_name: str
    kinds: tuple[CandidateKind, ...]

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the ``(app_label, model_name, field_name)`` lookup key."""
        return (self.app_label, self.model_name, self.field_name)

    def describe(self) -> str:
        """Return a description for a coverage failure message."""
        kinds = ", ".join(kind.value for kind in self.kinds)
        return f"{self.app_label}.{self.model_name}.{self.field_name} [{kinds}]"


def _user_model_label() -> str:
    """Return the configured ``AUTH_USER_MODEL`` in label form."""
    return settings.AUTH_USER_MODEL.lower()


def _targets_user(field: models.Field | ForeignObjectRel) -> bool:
    """Return True when *field* is a relation to ``AUTH_USER_MODEL``."""
    remote = getattr(field, "remote_field", None)
    related = getattr(remote, "model", None)
    meta = getattr(related, "_meta", None)
    return meta is not None and meta.label_lower == _user_model_label()


def _references_user(model: type[models.Model]) -> bool:
    """Return True when *model* has a forward relation to ``AUTH_USER_MODEL``."""
    return any(
        _targets_user(field)
        for field in model._meta.get_fields()
        if not field.auto_created
    )


def candidate_kinds(
    model: type[models.Model], field: models.Field | ForeignObjectRel
) -> tuple[CandidateKind, ...]:
    """Classify *field* under every candidate rule it matches, in rule order."""
    kinds: list[CandidateKind] = []
    if _targets_user(field):
        kinds.append(CandidateKind.USER_REFERENCE)
    if isinstance(field, models.EmailField):
        kinds.append(CandidateKind.EMAIL)
    if isinstance(field, models.GenericIPAddressField):
        kinds.append(CandidateKind.IP_ADDRESS)
    if isinstance(field, (models.FileField, models.ImageField)):
        kinds.append(CandidateKind.FILE)
    if isinstance(field, models.TextField) and _references_user(model):
        kinds.append(CandidateKind.FREE_TEXT)
    return tuple(kinds)


def walk_candidate_fields(
    model_classes: Iterable[type[models.Model]],
) -> list[CandidateField]:
    """Return every candidate field across *model_classes*."""
    candidates: list[CandidateField] = []
    for model in model_classes:
        for field in model._meta.get_fields():
            # Skip reverse relations and other auto-created field objects.
            if field.auto_created:
                continue
            kinds = candidate_kinds(model, field)
            if kinds:
                candidates.append(
                    CandidateField(
                        app_label=model._meta.app_label,
                        model_name=model.__name__,
                        field_name=field.name,
                        kinds=kinds,
                    )
                )
    return candidates


def uncovered_candidates(
    candidates: Iterable[CandidateField],
    fields: Iterable[PersonalDataField],
    exclusions: Iterable[PersonalDataExclusion],
) -> list[str]:
    """Return descriptions of candidates neither declared nor excluded."""
    covered = {entry.key for entry in fields}
    excluded = {entry.key for entry in exclusions if entry.reason.strip()}
    return [
        candidate.describe()
        for candidate in candidates
        if candidate.key not in covered and candidate.key not in excluded
    ]


def declared_personal_data() -> tuple[
    tuple[PersonalDataField, ...], tuple[PersonalDataExclusion, ...]
]:
    """Return the central rows plus every app's collected declarations.

    Rows are returned central-first, then in app-label order.  An entry that is
    neither a :class:`PersonalDataField` nor a :class:`PersonalDataExclusion`
    fails loudly instead of being read as a declaration with nothing to cover.
    """
    fields = list(CENTRAL_PERSONAL_DATA_FIELDS)
    exclusions = list(CENTRAL_PERSONAL_DATA_EXCLUSIONS)
    for declaration in collect_capabilities(PERSONAL_DATA_DECLARATIONS_CAPABILITY):
        if isinstance(declaration, PersonalDataField):
            fields.append(declaration)
        elif isinstance(declaration, PersonalDataExclusion):
            exclusions.append(declaration)
        else:
            raise ValueError(
                "The 'personal_data_declarations' capability must return "
                "PersonalDataField or PersonalDataExclusion entries; got "
                f"{declaration!r}."
            )
    return tuple(fields), tuple(exclusions)


def declared_treatment_handler_gaps() -> list[str]:
    """Return non-``KEEP_LINK`` declarations whose app declares no handler.

    A declared treatment other than ``KEEP_LINK`` promises work, and the
    anonymize boundary runs the declaring app's own ``anonymize_handlers``
    capability to do it.  Central rows are excluded by construction: their
    handler is not their app's (auth's scrub deletes allauth's and the
    sessions' rows, and orgs owns its own).
    """
    handlers = set(collect_capabilities("anonymize_handlers"))
    gaps: list[str] = []
    for declaration in collect_capabilities(PERSONAL_DATA_DECLARATIONS_CAPABILITY):
        if not isinstance(declaration, PersonalDataField):
            continue
        if declaration.treatment is PersonalDataTreatment.KEEP_LINK:
            continue
        name = (
            f"{declaration.app_label}.{declaration.model_name}."
            f"{declaration.field_name} [{declaration.treatment.value}]"
        )
        try:
            config = apps.get_app_config(declaration.app_label)
        except LookupError:
            gaps.append(f"{name} names an app that is not installed.")
            continue
        if config not in handlers:
            gaps.append(f"{name} has no anonymize_handlers capability.")
    return gaps


def personal_data_coverage_gaps() -> list[str]:
    """Return both kinds of personal-data declaration gap.

    The first is an undeclared candidate on a project-owned model: the walk
    covers every concrete model from a project-owned app — the installed
    QuickScale modules and any project app — so it is reported where the
    project's models are installed.  The second is a declared treatment whose
    declaring app provides no handler to execute it.
    """
    from quickscale_modules_orgs.tenancy import get_concrete_project_models

    fields, exclusions = declared_personal_data()
    return (
        uncovered_candidates(
            walk_candidate_fields(get_concrete_project_models()),
            fields,
            exclusions,
        )
        + declared_treatment_handler_gaps()
    )


# The rows no installed module declares for itself: orgs' own rows and the
# contrib/third-party rows (Django admin, sessions, and allauth's account).
CENTRAL_PERSONAL_DATA_FIELDS: tuple[PersonalDataField, ...] = (
    # -- allauth: login addresses exist only for sign-in --
    PersonalDataField(
        app_label="account",
        model_name="EmailAddress",
        field_name="user",
        treatment=PersonalDataTreatment.DELETE,
        note="Row deleted; verified and primary state go with it.",
    ),
    PersonalDataField(
        app_label="account",
        model_name="EmailAddress",
        field_name="email",
        treatment=PersonalDataTreatment.DELETE,
        note="Row deleted.",
    ),
    # -- sessions: active logins --
    PersonalDataField(
        app_label="sessions",
        model_name="Session",
        field_name="session_data",
        treatment=PersonalDataTreatment.DELETE,
        note="The person's session rows are deleted (session_key with them).",
    ),
    # -- orgs: membership and invitations --
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationMembership",
        field_name="user",
        treatment=PersonalDataTreatment.DELETE,
        note="The person leaves every organization; the last-owner guard still applies.",
    ),
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationMembership",
        field_name="invited_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Surviving memberships keep the inviter as deleted-user provenance.",
    ),
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationInvitation",
        field_name="email",
        treatment=PersonalDataTreatment.SCRUB,
        note="Pending invitations are withdrawn; accepted and expired rows keep "
        "the record with the address scrubbed.",
    ),
    PersonalDataField(
        app_label="quickscale_orgs",
        model_name="OrganizationInvitation",
        field_name="invited_by",
        treatment=PersonalDataTreatment.KEEP_LINK,
        note="Pending invitations are withdrawn; accepted rows keep the sender link.",
    ),
)

CENTRAL_PERSONAL_DATA_EXCLUSIONS: tuple[PersonalDataExclusion, ...] = (
    # -- Django admin: operator audit log, kept as written --
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="user",
        reason="Operator audit log; rows keep the link to the disabled account.",
    ),
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="object_id",
        reason="Operator audit record content; retained unchanged.",
    ),
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="change_message",
        reason="Operator audit record content; retained unchanged.",
    ),
    PersonalDataExclusion(
        app_label="admin",
        model_name="LogEntry",
        field_name="object_repr",
        reason="Operator audit record content (the acted-on object's display name); "
        "retained unchanged.",
    ),
)


def _shipped_models() -> Iterator[type[models.Model]]:
    """Yield every installed model that represents shipped data.

    Models from test-fixture apps and test modules are skipped: they register
    only when their test module is imported, so including them would make the
    inventory gate depend on collection order, and they hold no shipped data.
    """
    for model in apps.get_models(include_auto_created=True):
        module = model.__module__
        if module == "tests" or module.startswith("tests."):
            continue
        yield model


def shipped_candidate_fields() -> list[CandidateField]:
    """Return every candidate field across the installed shipped models."""
    return walk_candidate_fields(_shipped_models())
