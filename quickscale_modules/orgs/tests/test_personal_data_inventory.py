"""Personal-data inventory conformance gate (SA242).

The gate walks every installed model in the cross-module orgs harness --
``tests/settings.py`` installs every first-party module plus Django contrib,
allauth, and the orgs fixture apps -- and fails when a field that could hold
personal data about a user is neither listed in ``_personal_data_inventory``
with its treatment nor excluded there with a reason.

It lives in the orgs test suite for the same reason
``test_user_fk_conformance.py`` does: ``orgs/tests/settings.py`` is the
smallest truthful cross-module harness.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from tests._personal_data_inventory import (
    PERSONAL_DATA_EXCLUSIONS,
    PERSONAL_DATA_FIELDS,
    PersonalDataExclusion,
    PersonalDataField,
)

USER_MODEL_LABEL = settings.AUTH_USER_MODEL.lower()


class CandidateKind(enum.Enum):
    """A rule from SA242's scope that flags a field for classification."""

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
        """Return a description for a gate failure message."""
        kinds = ", ".join(kind.value for kind in self.kinds)
        return f"{self.app_label}.{self.model_name}.{self.field_name} [{kinds}]"


def _targets_user(field: models.Field) -> bool:
    """Return True when *field* is a relation to ``AUTH_USER_MODEL``."""
    remote = getattr(field, "remote_field", None)
    related = getattr(remote, "model", None)
    meta = getattr(related, "_meta", None)
    return meta is not None and meta.label_lower == USER_MODEL_LABEL


def _references_user(model: type[models.Model]) -> bool:
    """Return True when *model* has a forward relation to ``AUTH_USER_MODEL``."""
    return any(
        _targets_user(field)
        for field in model._meta.get_fields()
        if not field.auto_created
    )


def candidate_kinds(
    model: type[models.Model], field: models.Field
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


def _shipped_models() -> Iterator[type[models.Model]]:
    """Yield every installed model that represents shipped data.

    Models from test-fixture apps and test modules are skipped: they register
    only when their test module is imported, so including them would make this
    gate depend on collection order, and they hold no shipped data.
    """
    for model in apps.get_models(include_auto_created=True):
        module = model.__module__
        if module == "tests" or module.startswith("tests."):
            continue
        yield model


def walk_candidate_fields() -> list[CandidateField]:
    """Return every candidate field across the installed shipped models."""
    candidates: list[CandidateField] = []
    for model in _shipped_models():
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
    """Return descriptions of candidates neither inventoried nor excluded."""
    covered = {entry.key for entry in fields}
    excluded = {entry.key for entry in exclusions if entry.reason.strip()}
    return [
        candidate.describe()
        for candidate in candidates
        if candidate.key not in covered and candidate.key not in excluded
    ]


def _model_or_none(app_label: str, model_name: str) -> type[models.Model] | None:
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _has_field(model: type[models.Model], field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False
    return True


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_all_candidate_fields_are_inventoried_or_excluded() -> None:
    """Every candidate is listed with its treatment or excluded with a reason."""
    uncovered = uncovered_candidates(
        walk_candidate_fields(),
        PERSONAL_DATA_FIELDS,
        PERSONAL_DATA_EXCLUSIONS,
    )
    assert not uncovered, (
        "Personal-data candidates missing from "
        "quickscale_modules/orgs/tests/_personal_data_inventory.py. Add each "
        "field with its SA216 treatment, or an exclusion with a reason:\n"
        + "\n".join(uncovered)
    )


def test_candidate_rules_flag_each_representative_field() -> None:
    """The walk detects all five candidate rules, so the gate is not vacuous."""
    kinds_by_key = {
        candidate.key: candidate.kinds for candidate in walk_candidate_fields()
    }
    assert kinds_by_key[("account", "EmailAddress", "user")] == (
        CandidateKind.USER_REFERENCE,
    )
    assert CandidateKind.EMAIL in kinds_by_key[("account", "EmailAddress", "email")]
    assert (
        CandidateKind.IP_ADDRESS
        in kinds_by_key[("quickscale_forms", "FormSubmission", "ip_address")]
    )
    assert (
        CandidateKind.FILE
        in kinds_by_key[("quickscale_blog", "AuthorProfile", "avatar")]
    )
    assert (
        CandidateKind.FREE_TEXT
        in kinds_by_key[("quickscale_crm", "ContactNote", "text")]
    )


def test_inventory_and_exclusions_resolve_to_installed_fields() -> None:
    """Every entry names an installed model field, so none is stale."""
    for entry in (*PERSONAL_DATA_FIELDS, *PERSONAL_DATA_EXCLUSIONS):
        model = _model_or_none(entry.app_label, entry.model_name)
        assert model is not None, (
            f"Inventory entry {entry.app_label}.{entry.model_name}."
            f"{entry.field_name} does not resolve to an installed model."
        )
        assert _has_field(model, entry.field_name), (
            f"Inventory entry {entry.app_label}.{entry.model_name}."
            f"{entry.field_name} names a field the model does not have."
        )


def test_inventory_keys_are_unique_and_disjoint_from_exclusions() -> None:
    """No field is listed twice, and no field is both inventoried and excluded."""
    field_keys = [entry.key for entry in PERSONAL_DATA_FIELDS]
    exclusion_keys = [entry.key for entry in PERSONAL_DATA_EXCLUSIONS]
    assert len(field_keys) == len(set(field_keys)), "duplicate personal-data entry"
    assert len(exclusion_keys) == len(set(exclusion_keys)), "duplicate exclusion entry"
    assert not set(field_keys) & set(exclusion_keys), (
        "field both inventoried and excluded"
    )
    assert all(entry.reason.strip() for entry in PERSONAL_DATA_EXCLUSIONS), (
        "every exclusion must carry a non-blank reason"
    )


#: Fields confirmed to hold personal data that the candidate rules cannot see:
#: JSON payloads, sender-side text, and the user model's own names and secrets.
#: Deleting one of these entries would otherwise pass the metadata-driven gate.
_SEMANTIC_PERSONAL_DATA_KEYS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("quickscale_auth", "User", "username"),
        ("quickscale_auth", "User", "first_name"),
        ("quickscale_auth", "User", "last_name"),
        ("quickscale_auth", "User", "password"),
        ("quickscale_auth", "User", "last_login"),
        ("sessions", "Session", "session_data"),
        ("quickscale_notifications", "NotificationMessage", "subject"),
        ("quickscale_notifications", "NotificationMessage", "rendered_text"),
        ("quickscale_notifications", "NotificationMessage", "rendered_html"),
        ("quickscale_notifications", "NotificationMessage", "context_json"),
        ("quickscale_notifications", "NotificationMessage", "last_error"),
        ("quickscale_notifications", "NotificationDelivery", "failure_reason"),
        ("quickscale_notifications", "NotificationDeliveryEvent", "payload_json"),
        ("quickscale_billing", "WebhookEvent", "payload"),
    }
)


def test_semantic_personal_data_fields_stay_inventoried() -> None:
    """Fields the candidate rules cannot see must stay in the inventory."""
    inventoried = {entry.key for entry in PERSONAL_DATA_FIELDS}
    missing = _SEMANTIC_PERSONAL_DATA_KEYS - inventoried
    assert not missing, (
        f"Confirmed personal-data fields missing from the inventory: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# Controls: prove the gate fails on an unlisted field
# ---------------------------------------------------------------------------


def test_control_gate_fails_when_an_entry_is_missing() -> None:
    """Dropping one real entry makes the gate report its field."""
    candidates = walk_candidate_fields()
    target = next(
        candidate
        for candidate in candidates
        if candidate.key == ("account", "EmailAddress", "email")
    )
    assert CandidateKind.EMAIL in target.kinds
    reduced_fields = tuple(
        entry for entry in PERSONAL_DATA_FIELDS if entry.key != target.key
    )
    uncovered = uncovered_candidates(
        candidates, reduced_fields, PERSONAL_DATA_EXCLUSIONS
    )
    assert target.describe() in uncovered


def test_control_exclusion_with_a_reason_covers_a_candidate() -> None:
    """An explicit exclusion clears a candidate the rules flag."""
    model = apps.get_model("quickscale_forms", "FormSubmission")
    field = model._meta.get_field("ip_address")
    kinds = candidate_kinds(model, field)
    assert kinds == (CandidateKind.IP_ADDRESS,)
    candidate = CandidateField(
        app_label="quickscale_forms",
        model_name="FormSubmission",
        field_name="ip_address",
        kinds=kinds,
    )
    exclusion = PersonalDataExclusion(
        app_label="quickscale_forms",
        model_name="FormSubmission",
        field_name="ip_address",
        reason="control case",
    )
    assert uncovered_candidates([candidate], (), (exclusion,)) == []


def test_control_blank_exclusion_reason_is_rejected() -> None:
    """An exclusion without a reason does not clear a candidate."""
    model = apps.get_model("quickscale_forms", "FormSubmission")
    field = model._meta.get_field("ip_address")
    candidate = CandidateField(
        app_label="quickscale_forms",
        model_name="FormSubmission",
        field_name="ip_address",
        kinds=candidate_kinds(model, field),
    )
    blank = PersonalDataExclusion(
        app_label="quickscale_forms",
        model_name="FormSubmission",
        field_name="ip_address",
        reason="   ",
    )
    assert uncovered_candidates([candidate], (), (blank,)) == [candidate.describe()]
