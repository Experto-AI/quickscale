"""Helpers for materializing implicit module configs in CLI flows."""

from collections.abc import Collection
from typing import Any

from quickscale_cli.commands.module_config import get_default_notifications_config


def get_implied_module_default_configs(
    module_names: Collection[str],
) -> dict[str, dict[str, Any]]:
    """Return module config blocks that should be made explicit automatically."""
    names = set(module_names)
    implied_configs: dict[str, dict[str, Any]] = {}

    if "billing" in names and "orgs" not in names:
        implied_configs["orgs"] = {}
        names.add("orgs")

    if "crm" in names and "orgs" not in names:
        implied_configs["orgs"] = {}
        names.add("orgs")

    if "orgs" in names and "notifications" not in names:
        implied_configs["notifications"] = get_default_notifications_config()

    return implied_configs
