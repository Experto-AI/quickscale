"""Tests for social app configuration."""

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured


def test_social_app_config_matches_packaged_module_contract() -> None:
    """The packaged app config should expose the expected name, label, and title."""
    config = apps.get_app_config("quickscale_social")

    assert config.name == "quickscale_modules_social"
    assert config.label == "quickscale_social"
    assert config.verbose_name == "QuickScale Social"
    assert config.default_auto_field == "django.db.models.BigAutoField"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"QUICKSCALE_SOCIAL_LINK_TREE_ENABLED": "sometimes"},
            r"QUICKSCALE_SOCIAL_LINK_TREE_ENABLED.*must be a boolean",
        ),
        (
            {"QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE": 0},
            r"QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE.*must be >= 1",
        ),
        (
            {"QUICKSCALE_SOCIAL_LAYOUT_VARIANT": "mosaic"},
            r"QUICKSCALE_SOCIAL_LAYOUT_VARIANT.*must be one of: list, cards, grid",
        ),
        (
            {"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": []},
            r"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST.*cannot be empty",
        ),
        (
            {"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": ["youtube", "mastodon"]},
            r"contains unsupported values: mastodon",
        ),
        (
            {"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": ["linkedin"]},
            r"must include one of: tiktok, youtube",
        ),
        (
            {
                "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED": False,
                "QUICKSCALE_SOCIAL_EMBEDS_ENABLED": False,
            },
            r"is required",
        ),
    ],
)
def test_startup_check_refuses_an_invalid_declared_setting(
    settings, overrides: dict[str, object], message: str
) -> None:
    """Rule 3: an invalid declared setting fails startup naming the setting."""
    for name, value in overrides.items():
        setattr(settings, name, value)

    with pytest.raises(ImproperlyConfigured, match=message):
        apps.get_app_config("quickscale_social").ready()
