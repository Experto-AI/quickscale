"""Example backend extensions contract and wiring.

Copy this file into your generated project (for example into a `client_extensions/` app)
and add the app to `INSTALLED_APPS`. Keep the wiring idempotent to avoid duplicate
registrations during tests or multiple AppConfig.ready() calls.
"""

from django.apps import AppConfig


class ClientExtensionsConfig(AppConfig):
    name = "client_extensions"

    def ready(self):
        # Idempotent registration example
        from . import backend_extensions_impl

        backend_extensions_impl.register()


def register():
    """Simple registration hook called from AppConfig.ready().

    Implement any project-specific startup wiring here (signals, receivers,
    patching third-party behaviour, etc.). Keep this function fast and idempotent.
    """
    # Example: connect a signal handler (import inside function to avoid side-effects)
    try:
        from django.db.models.signals import post_save
        from django.contrib.auth import get_user_model

        def _on_user_save(sender, instance, created, **kwargs):
            if created:
                # perform lightweight onboarding tasks
                pass

        post_save.connect(_on_user_save, sender=get_user_model(), weak=False)
    except Exception:
        # Keep startup robust in minimal generated projects; log if needed.
        pass


if __name__ == "__main__":
    # Quick local test
    register()
"""Minimal example of a backend extensions registration module.

Place project-specific startup wiring here (signals, admin enhancements, feature
flags, optional integrations). Keep code idempotent and import-safe.
"""

def register():
    """Register project-specific backend extensions.

    This function should be safe to call multiple times and avoid side-effects on
    import. Prefer lazy imports inside the function so startup ordering is stable.
    """
    # Example: wire a signal handler lazily
    try:
        from django.db.models.signals import post_save

        def _on_save(sender, instance, created, **kwargs):
            # Put project-specific behavior here
            return None

        # In real code, guard registration to avoid double-binding
        # post_save.connect(_on_save, sender=MyModel)
    except Exception:
        # Keep example safe; real projects should log errors instead
        pass
