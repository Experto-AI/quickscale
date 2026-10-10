"""Contract tests for the shared DRF helper classes (SA262).

The one session authentication class keeps a 401 challenge for anonymous
callers, so every module session API and the generated settings share the
same scheme instead of a per-module copy.  The combined facade serves it
lazily; these tests hold that surface in place.
"""

from __future__ import annotations

from typing import cast

from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request

from quickscale_core.runtime import QuickscaleSessionAuthentication
from quickscale_core.runtime import drf as drf_helpers


class TestQuickscaleSessionAuthentication:
    """The core session authentication class declares the 401 challenge."""

    def test_is_the_one_session_authentication_class(self) -> None:
        assert issubclass(QuickscaleSessionAuthentication, SessionAuthentication)

    def test_anonymous_challenge_is_401(self) -> None:
        scheme = QuickscaleSessionAuthentication()
        assert scheme.authenticate_header(cast(Request, None)) == "Session"

    def test_facade_serves_the_submodule_symbol(self) -> None:
        assert (
            QuickscaleSessionAuthentication
            is drf_helpers.QuickscaleSessionAuthentication
        )
