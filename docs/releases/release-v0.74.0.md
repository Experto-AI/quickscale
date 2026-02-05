# Release v0.74.0 - React Default Theme (showcase_react)

**Release Date:** 2026-02-05
**Status:** ✅ Released

## Summary
This release marks a major milestone in QuickScale's evolution by establishing **React + shadcn/ui** as the default frontend foundation. All new projects generated with QuickScale now benefit from a modern, performant, and highly customizable React stack out of the box.

## What's New

### Features
- **Brand New `showcase_react` Theme**: A full-featured React template powered by Vite, TypeScript, and Tailwind CSS.
- **shadcn/ui Integration**: Pre-configured with essential components like Buttons, Cards, Inputs, and a modern Dashboard Sidebar.
- **Server State Management**: Integrated TanStack Query for efficient data fetching and caching from Django REST APIs.
- **Client State Management**: Light-weight state management using Zustand.
- **CLI Default Update**: `quickscale plan` and `quickscale apply` now default to the React theme, providing a modern starting point for every project.
- **Automated Testing**: Pre-configured Vitest and React Testing Library setup in generated projects.

### Improvements
- **Standardized Project Structure**: New projects follow a clean separation between Django backend and React frontend.
- **Improved CLI Feedback**: Better error handling and status reporting during the generation of React-based projects.
- **Responsive Layouts**: The default theme includes a fully responsive App shell with a collapsible sidebar.

### Bug Fixes
- Fixed CLI path issues when generating deep nested directory structures for React templates.
- Corrected Jinja2 template rendering for `package.json` to ensure valid versioning strings.

## Breaking Changes
- **Default Theme Change**: The default theme for new projects is now `showcase_react`. Users who prefer the classic HTML/HTMX approach can still specify it via `quickscale plan --theme showcase_html`, but React is now the primary path.

## Migration Guide
1. **Existing Projects**: No automatic migration is provided. Existing projects built with `showcase_html` will continue to work.
2. **Adopting React**: To move an existing project to the new React foundation, we recommend creating a new project with v0.74.0 and migrating your custom business logic.

## Known Issues
- `pnpm` is required on the user's system to install dependencies in the generated project automatically. If missing, users must install it or manually use `npm`/`yarn`.

## Validation
- ✅ Full Python test suite passing (./scripts/test_all.sh)
- ✅ Linting passing (./scripts/lint.sh)
- ✅ Manual verification of generated React projects
- ✅ E2E validation of `quickscale apply` with the new theme
