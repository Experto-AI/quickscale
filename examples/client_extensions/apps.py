from django.apps import AppConfig


class ClientExtensionsConfig(AppConfig):
    name = "client_extensions"
    verbose_name = "Project-specific client extensions"

    def ready(self):
        """
        Call the opt-in register hook if present when Django starts.

        Keep register() idempotent and safe to call multiple times. Avoid
        heavy work on import; do runtime imports inside functions.
        """
        try:
            from . import backend_extensions

            if hasattr(backend_extensions, "register"):
                backend_extensions.register()
        except Exception:
            # Don't crash project startup if the example contains placeholder code.
            # Replace with logging in real projects.
            pass
