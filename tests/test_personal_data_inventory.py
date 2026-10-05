"""Personal-data declaration conformance gate (Module Conventions rule 49).

The gate walks every installed model in the cross-module orgs harness --
``tests/settings.py`` installs every first-party module plus Django contrib,
allauth, and the orgs fixture apps -- and fails when a field that could hold
personal data about a user is neither declared with its treatment nor excluded
with a reason.  Each module declares the rows it owns through its ``AppConfig``
``personal_data_declarations`` capability, collected by
``quickscale_modules_orgs._personal_data.declared_personal_data``; that helper
adds the rows no installed module declares for itself (orgs' own, Django admin,
sessions, and allauth's account).

It lives in the orgs test suite for the same reason
``test_user_fk_conformance.py`` does: ``orgs/tests/settings.py`` is the
smallest truthful cross-module harness.
"""

from __future__ import annotations

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    collect_capabilities,
)
from quickscale_modules_orgs._personal_data import (
    CENTRAL_PERSONAL_DATA_EXCLUSIONS,
    CENTRAL_PERSONAL_DATA_FIELDS,
    PERSONAL_DATA_DECLARATIONS_CAPABILITY,
    CandidateField,
    CandidateKind,
    candidate_kinds,
    declared_personal_data,
    declared_treatment_handler_gaps,
    shipped_candidate_fields,
    uncovered_candidates,
)


def _declared_inventory() -> tuple[
    tuple[PersonalDataField, ...], tuple[PersonalDataExclusion, ...]
]:
    """Return the central rows plus every app's collected declarations."""
    return declared_personal_data()


def _model_or_none(app_label: str, model_name: str) -> type | None:
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _has_field(model: type, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False
    return True


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_all_candidate_fields_are_declared_or_excluded() -> None:
    """Every candidate is declared with its treatment or excluded with a reason."""
    fields, exclusions = _declared_inventory()
    uncovered = uncovered_candidates(
        shipped_candidate_fields(),
        fields,
        exclusions,
    )
    assert not uncovered, (
        "Personal-data candidates with no declared treatment. Declare each "
        "field's treatment, or an exclusion with a reason, in the owning "
        "app's 'personal_data_declarations' capability beside its "
        "anonymization handler (Module Conventions rule 49; see "
        "module-extension.md, Project-Owned Tenant Models):\n" + "\n".join(uncovered)
    )


def test_candidate_rules_flag_each_representative_field() -> None:
    """The walk detects all five candidate rules, so the gate is not vacuous."""
    kinds_by_key = {
        candidate.key: candidate.kinds for candidate in shipped_candidate_fields()
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
    fields, exclusions = _declared_inventory()
    for entry in (*fields, *exclusions):
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
    """No field is listed twice, and no field is both declared and excluded."""
    fields, exclusions = _declared_inventory()
    field_keys = [entry.key for entry in fields]
    exclusion_keys = [entry.key for entry in exclusions]
    assert len(field_keys) == len(set(field_keys)), "duplicate personal-data entry"
    assert len(exclusion_keys) == len(set(exclusion_keys)), "duplicate exclusion entry"
    assert not set(field_keys) & set(exclusion_keys), "field both declared and excluded"
    assert all(entry.reason.strip() for entry in exclusions), (
        "every exclusion must carry a non-blank reason"
    )


def test_central_rows_keep_only_orgs_contrib_and_third_party() -> None:
    """No module's rows stay in orgs' central file; each module declares them."""
    central_app_labels = {"quickscale_orgs", "account", "sessions", "admin"}
    for entry in (*CENTRAL_PERSONAL_DATA_FIELDS, *CENTRAL_PERSONAL_DATA_EXCLUSIONS):
        assert entry.app_label in central_app_labels, (
            f"{entry.app_label}.{entry.model_name}.{entry.field_name} is a "
            "module's own row and must be declared by that module, not kept "
            "in orgs' central file."
        )


def test_declared_treatments_other_than_keep_link_have_a_handler() -> None:
    """A declaration that promises work names the app that executes it."""
    declared = [
        entry
        for entry in collect_capabilities(PERSONAL_DATA_DECLARATIONS_CAPABILITY)
        if isinstance(entry, PersonalDataField)
    ]
    assert declared, "no app declares personal-data fields"
    assert declared_treatment_handler_gaps() == []


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
    fields, _ = _declared_inventory()
    inventoried = {entry.key for entry in fields}
    missing = _SEMANTIC_PERSONAL_DATA_KEYS - inventoried
    assert not missing, (
        f"Confirmed personal-data fields missing from the inventory: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# Controls: prove the gate fails on an unlisted field
# ---------------------------------------------------------------------------


def test_control_gate_fails_when_an_entry_is_missing() -> None:
    """Dropping one real entry makes the gate report its field."""
    fields, exclusions = _declared_inventory()
    candidates = shipped_candidate_fields()
    target = next(
        candidate
        for candidate in candidates
        if candidate.key == ("account", "EmailAddress", "email")
    )
    assert CandidateKind.EMAIL in target.kinds
    reduced_fields = tuple(entry for entry in fields if entry.key != target.key)
    uncovered = uncovered_candidates(candidates, reduced_fields, exclusions)
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
