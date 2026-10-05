"""Account-anonymization executor for notifications' personal data.

``QuickscaleNotificationsConfig.anonymize_account`` delegates here.  The
module declares the ``anonymize_handlers`` capability without declaring an
organization-removal obligation: a generated project may embed notifications
without ``orgs``, and the declaration vocabulary lives in the orgs package, so
the anonymize boundary collects this handler through the shared core
helper exactly like the other declared handlers.

Only the messages linked to the person are scrubbed: the ones delivered to
them, the ones whose ``context_json`` records them as the actor through an
``actor_user_id`` key that ``send_notification`` callers stamp, and — the
pre-key fallback — the ones whose ``context_json`` carries their unique
address.  An invitation message is delivered to the invitee but renders the
inviter's name, so the actor link, not delivery, selects the inviter's
records.  A message delivered only to the person has every rendered field
replaced wholesale, as the inventory's treatment reads; any other linked
message keeps the content that is not about the person and loses each
occurrence of their address, full name, and username — in the raw and
HTML-escaped spellings Django rendering stores.  The person's own delivery
rows and provider event payloads are scrubbed regardless.  The fallback
matches their address, which is unique, and never their name, which can be an
ordinary word; a name match cannot select another person's message.  An
invitation message sent before the actor key existed names only the inviter's
display name, so it carries no link the fallback can match and stays as
stored — a recorded limit, not a selector.
"""

from __future__ import annotations

import re
from typing import Any

from django.utils.html import escape as html_escape

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
)

#: Replaces rendered text and provider error text that echoed the person.
REDACTED = "[redacted]"

#: Matches one complete email address.  A replacement is decided per complete
#: match, never per raw substring, so ``test@example.com`` found inside
#: ``protest@example.com`` cannot rewrite another person's address.
_ADDRESS_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
)

#: Quote delimiters an address is commonly wrapped in inside free text.
_QUOTE_CHARS = "'\""


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    """Scrub the person's deliveries, event payloads, and linked messages.

    ``original_name`` and ``original_username`` are the pre-scrub display
    spellings — the invitation email renders the full name, falling back to
    the username — removed from every linked message that carries them.  A
    message is linked when a delivery addresses the person, when its
    ``context_json`` names them as the actor, or when it carries their unique
    address; no other message is read or rewritten.
    """
    email = original_email.strip()
    if not email:
        return
    name = original_name.strip()
    username = original_username.strip()
    if username.casefold() in {email.casefold(), name.casefold()}:
        username = ""
    deleted_address = f"deleted-{user.pk}@invalid"

    delivery_ids = list(
        NotificationDelivery.objects.filter(recipient_email__iexact=email).values_list(
            "pk", flat=True
        )
    )
    if delivery_ids:
        NotificationDelivery.objects.filter(
            pk__in=delivery_ids,
            failure_reason__gt="",
        ).update(failure_reason=REDACTED)
        NotificationDelivery.objects.filter(pk__in=delivery_ids).update(
            recipient_email=deleted_address
        )
        _scrub_event_payloads(delivery_ids, email=email, replacement=deleted_address)

    _scrub_messages(
        user,
        delivery_ids,
        email=email,
        name=name,
        username=username,
        deleted_address=deleted_address,
    )


def _scrub_event_payloads(
    delivery_ids: list[Any],
    *,
    email: str,
    replacement: str,
) -> None:
    """Replace the person's address inside each provider event payload."""
    events = NotificationDeliveryEvent.objects.filter(delivery_id__in=delivery_ids)
    for event in events.iterator():
        redacted = _redact_email(
            event.payload_json, email=email, replacement=replacement
        )
        if redacted != event.payload_json:
            event.payload_json = redacted
            event.save(update_fields=["payload_json"])


def _scrub_messages(
    user: Any,
    delivery_ids: list[Any],
    *,
    email: str,
    name: str,
    username: str,
    deleted_address: str,
) -> None:
    """Redact the messages linked to the person, and only those.

    Three links select a message: a delivery to the person, an
    ``actor_user_id`` context entry naming them as the actor, or — the
    pre-key fallback — their unique address inside ``context_json``.  The
    fallback verifies a complete address, never a name, so a namesake's
    address or an ordinary word cannot select another person's message.
    """
    person_message_ids = set(
        NotificationDelivery.objects.filter(pk__in=delivery_ids).values_list(
            "message_id", flat=True
        )
    )
    actor_message_ids = set(
        NotificationMessage.objects.filter(
            context_json__actor_user_id=str(user.pk)
        ).values_list("pk", flat=True)
    )
    fallback_message_ids = {
        pk
        for pk, context in NotificationMessage.objects.filter(
            context_json__icontains=email
        ).values_list("pk", "context_json")
        if _context_names_the_address(context, email=email)
    }
    candidate_ids = person_message_ids | actor_message_ids | fallback_message_ids
    if not candidate_ids:
        return
    shared_message_ids = set(
        NotificationDelivery.objects.filter(message_id__in=candidate_ids)
        .exclude(pk__in=delivery_ids)
        .values_list("message_id", flat=True)
    )
    for message in NotificationMessage.objects.filter(pk__in=candidate_ids).iterator():
        if message.pk in person_message_ids and message.pk not in shared_message_ids:
            _redact_message_wholesale(message)
        else:
            _redact_message_identity(
                message,
                email=email,
                name=name,
                username=username,
                deleted_address=deleted_address,
            )


def _redact_message_wholesale(message: NotificationMessage) -> None:
    """Replace every rendered field of a message sent only to the person."""
    redacted_fields: list[str] = []
    for field_name in ("subject", "rendered_text", "rendered_html", "last_error"):
        if getattr(message, field_name):
            setattr(message, field_name, REDACTED)
            redacted_fields.append(field_name)
    if message.context_json:
        message.context_json = {}
        redacted_fields.append("context_json")
    if redacted_fields:
        message.save(update_fields=redacted_fields)


def _redact_message_identity(
    message: NotificationMessage,
    *,
    email: str,
    name: str,
    username: str,
    deleted_address: str,
) -> None:
    """Replace the person's identity inside a message's rendered fields."""
    redacted_fields: list[str] = []
    for field_name in ("subject", "rendered_text", "rendered_html", "last_error"):
        value = getattr(message, field_name)
        if not value:
            continue
        scrubbed = _redact_identity_text(
            value,
            email=email,
            name=name,
            username=username,
            email_replacement=deleted_address,
        )
        if scrubbed != value:
            setattr(message, field_name, scrubbed)
            redacted_fields.append(field_name)
    if message.context_json:
        scrubbed_context = _redact_identity_tree(
            message.context_json,
            email=email,
            name=name,
            username=username,
            email_replacement=deleted_address,
        )
        if scrubbed_context != message.context_json:
            message.context_json = scrubbed_context
            redacted_fields.append("context_json")
    if redacted_fields:
        message.save(update_fields=redacted_fields)


def _identity_spellings(value: str) -> tuple[str, ...]:
    """Return the raw and HTML-escaped spellings of a rendered identity.

    A rendered message stores an identity as the template's escaping produced
    it (``Anne O'Connor`` becomes ``Anne O&#x27;Connor``), so replacing only
    the raw spelling would leave the escaped one behind.
    """
    escaped = html_escape(value)
    if escaped == value:
        return (value,)
    return (value, escaped)


#: Every character an email local part may carry, used to decide whether an
#: escaped-spelling occurrence continues another address.
_LOCAL_PART_CHARS = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.!#$%&'*+/=?^_`{|}~-"
)

#: The entity decoding to an ampersand, a genuine local-part character: an
#: occurrence after it continues the address the ampersand starts
#: (``&amp;o&#x27;connor@example.com`` is ``&o'connor@example.com``).
_AMPERSAND_ENTITY = "&amp;"

#: HTML entities that decode to quote characters; at a token boundary they are
#: rendered quotation delimiters, not local-part characters
#: (``&#x27;o&#x27;connor@example.com&#x27;`` is a quoted address), unless the
#: text before them already continues a local part.
_QUOTE_ENTITIES = ("&#x27;", "&#39;", "&quot;", "&apos;")

#: Matches one address token in either raw or HTML-escaped rendering, used to
#: keep name/username redaction out of complete unrelated addresses.
_ADDRESS_OR_ESCAPED_PATTERN = re.compile(
    r"(?:(?:&[A-Za-z0-9#]+;)|[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])+"
    r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
)


def _redact_identity_text(
    value: str,
    *,
    email: str,
    name: str,
    username: str,
    email_replacement: str,
) -> str:
    """Replace the person's identity inside one stored string.

    The escaped email spelling is replaced only when it is not part of another
    address (an entity ending another local part included); names and
    usernames are replaced at word boundaries and never inside a complete
    address, so a short name cannot rewrite an unrelated word or another
    person's address.
    """
    value = _replace_escaped_email(value, email=email, replacement=email_replacement)
    value = _replace_addresses(value, email=email, replacement=email_replacement)
    if name or username:
        value = _redact_names_outside_addresses(value, name=name, username=username)
    return value


def _replace_escaped_email(value: str, *, email: str, replacement: str) -> str:
    """Replace the HTML-escaped spelling of *email* outside other addresses."""
    for spelling in _identity_spellings(email):
        if spelling == email:
            continue
        value = _replace_escaped_occurrences(
            value, spelling=spelling, replacement=replacement
        )
    return value


def _replace_escaped_occurrences(
    value: str,
    *,
    spelling: str,
    replacement: str,
) -> str:
    """Replace *spelling* unless an occurrence continues a longer address."""
    pattern = re.compile(re.escape(spelling), re.IGNORECASE)
    parts: list[str] = []
    last = 0
    for match in pattern.finditer(value):
        if _continues_address(value, match.start(), match.end()):
            continue
        parts.append(value[last : match.start()])
        parts.append(replacement)
        last = match.end()
    parts.append(value[last:])
    return "".join(parts)


def _continues_address(value: str, start: int, end: int) -> bool:
    """Return whether the occurrence continues an address on either side."""
    if start > 0 and _continues_before(value, start):
        return True
    return end < len(value) and _continues_after(value, end)


def _continues_before(value: str, index: int) -> bool:
    """Return whether the text before *index* continues a local part.

    A quote entity at a token boundary is the rendered form of a quotation
    delimiter, not a local-part character: ``&#x27;o&#x27;connor@...`` is a
    quoted address, while ``x&amp;o&#x27;connor@...`` continues the local part
    that the entity's leading text started.
    """
    char = value[index - 1]
    if char in _LOCAL_PART_CHARS:
        return True
    if char == ";":
        return _entity_chain_continues_local_part(value[:index])
    return False


def _entity_chain_continues_local_part(prefix: str) -> bool:
    """Return whether the trailing entity chain sits inside a local part.

    An ampersand entity is a genuine local-part character, so it always
    continues the address; a quote entity only continues one when the text
    before it is itself local-part text or entities.  The whole trailing chain
    is walked, however long, so an ampersand behind several quote entities is
    still recognized.
    """
    while prefix:
        if prefix.endswith(_AMPERSAND_ENTITY):
            return True
        matched = next(
            (entity for entity in _QUOTE_ENTITIES if prefix.endswith(entity)),
            None,
        )
        if matched is None:
            return False
        prefix = prefix[: -len(matched)]
        if not prefix:
            return False
        if prefix[-1] in _LOCAL_PART_CHARS:
            return True
    return False


def _continues_after(value: str, index: int) -> bool:
    """Return whether the text at *index* continues an address domain."""
    char = value[index]
    if char.isalnum() or char == "-":
        return True
    return char == "." and index + 1 < len(value) and value[index + 1].isalnum()


def _redact_names_outside_addresses(
    value: str,
    *,
    name: str,
    username: str,
) -> str:
    """Replace name and username spellings, leaving every address intact.

    The split recognizes raw and HTML-escaped address tokens alike, so a name
    cannot rewrite the local part of an unrelated rendered address
    (``ann&amp;smith@example.com``).
    """
    parts: list[str] = []
    last = 0
    for match in _ADDRESS_OR_ESCAPED_PATTERN.finditer(value):
        parts.append(
            _redact_names(value[last : match.start()], name=name, username=username)
        )
        parts.append(match.group(0))
        last = match.end()
    parts.append(_redact_names(value[last:], name=name, username=username))
    return "".join(parts)


def _redact_names(value: str, *, name: str, username: str) -> str:
    """Replace name and username spellings at word boundaries in *value*."""
    if name:
        for spelling in _identity_spellings(name):
            value = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(spelling)}(?![A-Za-z0-9_])",
                REDACTED,
                value,
                flags=re.IGNORECASE,
            )
    if username:
        for spelling in _identity_spellings(username):
            value = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(spelling)}(?![A-Za-z0-9_])",
                REDACTED,
                value,
                flags=re.IGNORECASE,
            )
    return value


def _redact_identity_tree(
    value: Any,
    *,
    email: str,
    name: str,
    username: str,
    email_replacement: str,
) -> Any:
    """Replace the person's identity in every string of a JSON value.

    JSON object keys are strings too, so an identity-keyed context entry is
    redacted as well as its value.
    """
    if isinstance(value, dict):
        return {
            _redact_identity_text(
                str(key),
                email=email,
                name=name,
                username=username,
                email_replacement=email_replacement,
            ): _redact_identity_tree(
                item,
                email=email,
                name=name,
                username=username,
                email_replacement=email_replacement,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_identity_tree(
                item,
                email=email,
                name=name,
                username=username,
                email_replacement=email_replacement,
            )
            for item in value
        ]
    if isinstance(value, str):
        return _redact_identity_text(
            value,
            email=email,
            name=name,
            username=username,
            email_replacement=email_replacement,
        )
    return value


def _redact_email(value: Any, *, email: str, replacement: str) -> Any:
    """Return *value* with the person's address replaced, structure preserved."""
    if isinstance(value, dict):
        return {
            _replace_addresses(str(key), email=email, replacement=replacement): (
                _redact_email(item, email=email, replacement=replacement)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_email(item, email=email, replacement=replacement) for item in value
        ]
    if isinstance(value, str):
        return _replace_addresses(value, email=email, replacement=replacement)
    return value


def _identity_form(token: str, target: str) -> str | None:
    """Return the quote prefix under which *token* is *target*, or ``None``.

    A quoted occurrence adds a delimiter quote in front of the address, and an
    address may itself start with a quote, so the token is compared after
    dropping zero, one, or more leading quote delimiters; the dropped prefix
    is returned so a replacement can keep the quoting.  Trailing quotes are
    outside the domain-ending token and stay in the surrounding text.
    """
    for count in range(len(token) + 1):
        prefix = token[:count]
        if any(char not in _QUOTE_CHARS for char in prefix):
            return None
        if token[count:].casefold() == target:
            return prefix
    return None


def _carries_address(value: str, *, email: str) -> bool:
    """Return whether *value* holds *email* as one complete address."""
    return _replace_addresses(value, email=email, replacement="") != value


def _context_names_the_address(value: Any, *, email: str) -> bool:
    """Return whether a stored context carries the person's complete address.

    JSON object keys are strings too, so a context key naming the address
    counts, exactly as the redaction tree treats keys.
    """
    if isinstance(value, dict):
        return any(
            _context_names_the_address(str(key), email=email)
            or _context_names_the_address(item, email=email)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_context_names_the_address(item, email=email) for item in value)
    if isinstance(value, str):
        return _carries_address(value, email=email)
    return False


def _replace_addresses(value: str, *, email: str, replacement: str) -> str:
    """Replace every complete occurrence of *email*, leaving other addresses.

    A token is compared as it stands first, so an address whose own local part
    starts with a quote (``'test@example.com``) still matches; then ordinary
    quote delimiters may be dropped one at a time, so a quoted occurrence
    (``''test@example.com'`` around such an address) matches with the dropped
    quotes preserved around the replacement.  An address merely containing the
    target (``protest@example.com``) never matches.
    """
    if not value:
        return value
    target = email.casefold()

    def replace(match: re.Match[str]) -> str:
        prefix = _identity_form(match.group(0), target)
        if prefix is None:
            return match.group(0)
        return f"{prefix}{replacement}"

    return _ADDRESS_PATTERN.sub(replace, value)
