"""Context processors for QuickScale core functionality"""

from typing import Any

from django.apps import apps
from django.conf import settings
from django.http import HttpRequest

from quickscale_core.config.module_config import load_config


def _is_saas_mode() -> bool:
    try:
        return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
    except Exception:
        return False


def _resolve_compatibility_organization_for_user(user: Any) -> tuple[Any | None, bool]:
    if not getattr(user, "is_authenticated", False) or not _is_saas_mode():
        return None, False

    try:
        if not apps.is_installed("quickscale_modules_orgs"):
            return None, False
        membership_model = apps.get_model(
            "quickscale_modules_orgs",
            "OrganizationMembership",
        )
    except Exception:
        return None, False

    try:
        memberships = list(
            membership_model.objects.select_related("organization")
            .filter(user=user)
            .order_by("organization__name", "organization__pk")[:2]
        )
    except Exception:
        return None, False

    if len(memberships) == 1:
        return memberships[0].organization, False
    return None, len(memberships) > 1


def _billing_route_organization(organization: Any | None) -> Any | None:
    org_slug = getattr(organization, "slug", None)
    if not _is_saas_mode():
        return None
    if isinstance(org_slug, str) and org_slug:
        return organization
    return None


def _pricing_url_for_organization(organization: Any | None) -> str:
    route_organization = _billing_route_organization(organization)
    org_slug = getattr(route_organization, "slug", None)
    if isinstance(org_slug, str) and org_slug:
        return f"/orgs/{org_slug}/billing/pricing/"
    return "/billing/pricing/"


def _user_has_owner_billing_access(*, user: Any, organization: Any | None) -> bool:
    if organization is None or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    try:
        if not apps.is_installed("quickscale_modules_orgs"):
            return False
        membership_model = apps.get_model(
            "quickscale_modules_orgs",
            "OrganizationMembership",
        )
    except Exception:
        return False

    try:
        return bool(
            membership_model.objects.filter(
                user=user,
                organization=organization,
                role="owner",
            ).exists()
        )
    except Exception:
        return False


def _billing_dashboard_url(request: HttpRequest | None) -> str:
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return "/billing/pricing/"

    organization = _billing_route_organization(getattr(request, "org", None))
    org_slug = getattr(organization, "slug", None)
    if isinstance(org_slug, str) and org_slug:
        if _user_has_owner_billing_access(user=user, organization=organization):
            return f"/orgs/{org_slug}/billing/dashboard/"
        return _pricing_url_for_organization(organization)

    compatibility_organization, ambiguous = (
        _resolve_compatibility_organization_for_user(user)
    )
    compatibility_org_slug = getattr(compatibility_organization, "slug", None)
    if isinstance(compatibility_org_slug, str) and compatibility_org_slug:
        if _user_has_owner_billing_access(
            user=user,
            organization=compatibility_organization,
        ):
            return f"/orgs/{compatibility_org_slug}/billing/dashboard/"
        return _pricing_url_for_organization(compatibility_organization)

    if _is_saas_mode():
        return "/orgs/" if ambiguous else "/orgs/new/"

    return "/billing/dashboard/"


def installed_modules(request: HttpRequest) -> dict[str, Any]:
    """Add installed modules information to all templates"""
    try:
        # Load module configuration
        config = load_config()

        # Define shipped modules and their navigation info
        available_modules = {
            "auth": {
                "name": "Authentication",
                "url": "quickscale_auth:profile",
                "icon": "👤",
            },
            "billing": {
                "name": "Billing",
                "url": _billing_dashboard_url(request),
                "icon": "💳",
            },
        }

        # Check which modules are installed and add navigation info
        modules = {}
        for module_name, module_info in available_modules.items():
            is_installed = module_name in config.modules
            modules[module_name] = {
                "installed": is_installed,
                "name": module_info["name"],
                "url": module_info["url"],
                "icon": module_info["icon"],
                "css_class": "nav-link" + (" disabled" if not is_installed else ""),
            }

        return {"modules": modules}
    except Exception:
        # If there's any error loading config, return empty modules dict
        return {"modules": {}}
