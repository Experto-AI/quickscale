"""Context processors for QuickScale core functionality"""

from typing import Any

from django.http import HttpRequest

from quickscale_core.config.module_config import load_config


def installed_modules(request: HttpRequest) -> dict[str, Any]:
    """Add installed modules information to all templates"""
    try:
        # Load module configuration
        config = load_config()

        # Define available modules and their navigation info
        available_modules = {
            "auth": {
                "name": "Authentication",
                "url": "quickscale_auth:profile",
                "icon": "👤",
            },
            "billing": {
                "name": "Billing",
                "url": "billing:dashboard",  # This would need to be defined in billing module
                "icon": "💳",
            },
            "teams": {
                "name": "Teams",
                "url": "teams:dashboard",  # This would need to be defined in teams module
                "icon": "👥",
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
