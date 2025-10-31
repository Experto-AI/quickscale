"""Example backend extensions for Django project customization."""

import logging
from typing import Any

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ClientExtensionsConfig(AppConfig):
    """Django app configuration for client-specific extensions."""

    name = "client_extensions"

    def ready(self) -> None:
        """Initialize backend extensions when Django starts."""
        from . import backend_extensions_impl

        backend_extensions_impl.register()


def register() -> None:
    """Register project-specific backend extensions and startup wiring."""
    # Example: Connect a signal handler with lazy import
    try:
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        def _on_user_save(
            sender: Any, instance: Any, created: bool, **kwargs: Any
        ) -> None:
            """Handle user creation events for onboarding tasks."""
            if created:
                # Perform lightweight onboarding tasks
                logger.info(f"New user created: {instance.pk}")

        post_save.connect(_on_user_save, sender=get_user_model(), weak=False)
    except ImportError as e:
        logger.warning(f"Could not register user signal handler: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during extension registration: {e}")
        raise


if __name__ == "__main__":
    # Quick local test
    register()
