"""Sanitization helpers for rendered HTML links."""

import re

__all__ = ["sanitize_href", "sanitize_rendered_html"]

_ALLOWED_HREF_SCHEMES = frozenset({"http", "https", "mailto"})

# Regex matching a URI scheme at the start of an href value.
# RFC 3986: scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:")
_ATTR_HREF_RE = re.compile(r'href\s*=\s*"([^"]*)"', re.IGNORECASE)


def sanitize_href(href_value: str) -> str:
    """Return *href_value* if its URI scheme is allowed, or ``""`` otherwise.

    Allows ``http:``, ``https:``, ``mailto:``, relative URLs (no scheme),
    protocol-relative URLs (``//``), and fragment-only values. All other
    schemes (``javascript:``, ``data:``, ``vbscript:``, …) are neutralised
    so they cannot execute script in the browser.

    C0 control characters (``\\t``, ``\\r``, ``\\n``) and leading whitespace
    are stripped before the scheme check because browsers strip them from
    URLs before scheme parsing — without this, an obfuscated scheme such as
    ``java\\tscript:`` would bypass the allowlist.
    """
    if not href_value:
        return href_value

    # Browsers strip \t, \r, \n from URLs and trim leading C0
    # controls/whitespace before scheme parsing (WHATWG URL spec).
    # Normalise first so an obfuscated scheme cannot slip past the allowlist
    # regex, which excludes these characters from the scheme character class.
    cleaned = href_value.replace("\t", "").replace("\r", "").replace("\n", "").lstrip()

    if not _URI_SCHEME_RE.match(cleaned):
        # Relative, protocol-relative, or fragment — always safe.
        return cleaned

    scheme = cleaned.split(":", 1)[0].lower()
    if scheme in _ALLOWED_HREF_SCHEMES:
        return cleaned

    return ""


def sanitize_rendered_html(html: str) -> str:
    """Neutralise dangerous URI schemes in double-quoted ``href`` attributes.

    Runs rendered HTML through an allowlist scheme check so that only
    ``http:``, ``https:``, ``mailto:``, relative, protocol-relative, and
    fragment links survive. All other href values are replaced with an empty
    string.
    """
    return _ATTR_HREF_RE.sub(
        lambda match: 'href="' + sanitize_href(match.group(1)) + '"',
        html,
    )
