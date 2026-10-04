# Project-owned brand assets

Keep logos, marks, and other brand files here and import them from components
(`import logo from "../design/brand/logo.svg"`) or reference them from
`../tokens.css`. The served site favicon stays at `frontend/public/favicon.svg`
so Django's `{% static 'frontend/favicon.svg' %}` link keeps working.

This folder belongs to the project's design layer: no QuickScale command or
upgrade overwrites it. See `docs/technical/generated_file_ownership.md`.
