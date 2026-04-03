# Client extensions example

This folder contains a minimal example showing how a generated QuickScale project can expose a single, discoverable place for project-specific backend customizations without changing the generator.

This pattern is currently opt-in. It will become a default-generated first-class app in a future release.

How to use in a generated project:

1. Copy the `client_extensions/` directory into your generated project's repository (next to `manage.py`) or move `backend_extensions.py` into an existing local app.
2. Add `client_extensions` to `INSTALLED_APPS` if you keep the provided `AppConfig` wiring.
3. Implement `backend_extensions.register()` with your project-specific wiring such as signals, admin enhancements, or optional integrations.

Design notes:
- `AppConfig.ready()` calls `backend_extensions.register()` if present.
- Keep `register()` idempotent and avoid side effects on import.

See also: [Module Extension Contract](../../docs/technical/module-extension.md)
