"""Tests for the orgs-owned rendered-link sanitization API."""

import pytest

from quickscale_modules_orgs.sanitization import (
    sanitize_href,
    sanitize_rendered_html,
)


@pytest.mark.parametrize(
    ("href_value", "expected"),
    [
        ("", ""),
        ("java\tscript:alert(1)", ""),
        ("java\rscript:alert(1)", ""),
        ("java\nscript:alert(1)", ""),
        ("\t  javascript:alert(1)", ""),
        ("JaVaScRiPt:alert(1)", ""),
        ("data:text/html,test", ""),
        ("vbscript:msgbox(1)", ""),
        ("HTTP://example.com/page", "HTTP://example.com/page"),
        ("HtTpS://example.com/page", "HtTpS://example.com/page"),
        ("MAILTO:user@example.com", "MAILTO:user@example.com"),
        ("/relative/path", "/relative/path"),
        ("//cdn.example.com/path", "//cdn.example.com/path"),
        ("#fragment", "#fragment"),
    ],
)
def test_sanitize_href_preserves_allowed_values_and_blocks_other_schemes(
    href_value: str, expected: str
) -> None:
    """The public href primitive preserves allowed links and blocks schemes."""
    assert sanitize_href(href_value) == expected


def test_sanitize_rendered_html_only_rewrites_double_quoted_href_attributes() -> None:
    """Substitution is case-insensitive but limited to double-quoted hrefs."""
    rendered = (
        '<a HREF = "JaVaScRiPt:alert(1)">blocked</a>'
        " <a href='javascript:alert(2)'>single-quoted</a>"
        ' <a href="https://example.com">safe</a>'
    )

    assert sanitize_rendered_html(rendered) == (
        '<a href="">blocked</a>'
        " <a href='javascript:alert(2)'>single-quoted</a>"
        ' <a href="https://example.com">safe</a>'
    )


def test_sanitize_rendered_html_normalizes_href_before_scheme_check() -> None:
    """Control characters and leading whitespace are normalized in HTML hrefs."""
    assert sanitize_rendered_html('<a href="\t  HTTPS://example.com">safe</a>') == (
        '<a href="HTTPS://example.com">safe</a>'
    )
