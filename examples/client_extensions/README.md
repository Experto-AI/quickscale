# Client extensions example

This folder contains a minimal, opt-in example showing how a generated QuickScale project can expose a single, discoverable place for project-specific backend customizations without changing the generator.

How to use in a generated project:

1. Copy the `client_extensions/` directory into your generated project's repository (next to `manage.py`) or move `backend_extensions.py` into an existing local app.
2. Add `client_extensions` to `INSTALLED_APPS` if you keep the provided `AppConfig` wiring.
3. Implement `backend_extensions.register()` with your project-specific wiring such as signals, admin enhancements, or optional integrations.

Design notes:
- `AppConfig.ready()` calls `backend_extensions.register()` if present.
- Keep `register()` idempotent and avoid side effects on import.
- This is an opt-in pattern. The MVP generator keeps generated projects minimal and does not include this directory by default.

See also: [Backend Extensions Policy](../../docs/technical/decisions.md#backend-extensions-policy)
