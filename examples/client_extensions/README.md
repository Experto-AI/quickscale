# Client extensions example

This folder contains a minimal example showing how a generated QuickScale project can expose a single, discoverable place for project-specific backend customizations.

Usage:

1. Copy `backend_extensions.py` into your generated project root (next to `manage.py`) or into a local app like `client_extensions/`.
2. Add the app (for example `client_extensions`) to `INSTALLED_APPS` if you place the wiring inside an AppConfig.
3. See the example `AppConfig.ready()` implementation for idempotent startup wiring.

See also: [DECISIONS.md Backend Extensions Policy](../../DECISIONS.md#backend-extensions-policy)
# Example: client_extensions (opt-in)

This small example demonstrates a minimal, discoverable extension point for
project-specific backend wiring without changing QuickScale's generator.

How to use in a generated project:

1. Copy the `client_extensions/` directory into your generated project's
   repository (next to `manage.py`).
2. Add `client_extensions` to `INSTALLED_APPS` in your settings.
3. Implement `backend_extensions.register()` with your project-specific
   wiring (signals, admin enhancements, optional integrations).

Design notes:
- `AppConfig.ready()` calls `backend_extensions.register()` if present.
- Keep `register()` idempotent and avoid side effects on import.
- This is an opt-in pattern. The MVP generator keeps the project minimal and
  does not include this file by default.
