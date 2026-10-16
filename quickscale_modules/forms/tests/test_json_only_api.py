"""The forms API under the generated ``REST_FRAMEWORK`` defaults.

The generated settings compose ``REST_FRAMEWORK`` through
``quickscale_core.runtime.settings.compose_rest_framework``; the composed
defaults make module APIs JSON-only.  This suite proves what a generated
project does with a form-encoded public submit body: the composed parser
default refuses it with ``415`` in the one QuickScale error shape, while the
same payload as JSON still submits.  The suite's own settings do not compose
the defaults, so the test applies the composed value itself.
"""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from quickscale_core.runtime.settings import compose_rest_framework


@pytest.fixture(autouse=True)
def clear_forms_test_cache():
    """Keep throttle-backed API tests isolated across the module."""
    cache.clear()
    yield
    cache.clear()


def _generated_rest_framework() -> dict[str, object]:
    """Return the ``REST_FRAMEWORK`` a generated project composes here."""
    return compose_rest_framework(
        settings.REST_FRAMEWORK,
        use_x_forwarded_for=False,
        trusted_proxy_count=0,
    )


@pytest.mark.django_db
class TestFormsJsonOnlyAPI:
    """The public submit refuses a form-encoded body under the composed defaults.

    DRF binds ``APIView``'s policy classes on the class at import time, so
    ``override_settings`` alone cannot change them; the test binds the
    composed parser list itself, the way the generated settings bind it at
    startup (the same pattern this suite's throttle test uses for
    ``ScopedRateThrottle.THROTTLE_RATES``).
    """

    def test_submit_refuses_a_form_encoded_body(
        self, api_client, form, form_field, email_field
    ):
        """JSON submits; the same payload form-encoded is refused 415."""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        payload = {"full_name": "Alice", "email": "alice@example.com"}
        composed = _generated_rest_framework()

        with override_settings(REST_FRAMEWORK=composed):
            resolved_parsers = api_settings.DEFAULT_PARSER_CLASSES
            with patch.object(APIView, "parser_classes", resolved_parsers):
                submitted = api_client.post(url, data=payload, format="json")
                refused = api_client.post(
                    url,
                    data=urlencode(payload),
                    content_type="application/x-www-form-urlencoded",
                )

        assert submitted.status_code == status.HTTP_201_CREATED
        assert refused.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert refused.data["error"]["code"] == "unsupported_media_type"
