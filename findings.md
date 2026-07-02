# Structural Autopsy: QuickScale

> **Status: Closed 2026-07-02.** The 2026-06-30 autopsy identified 5 findings; all were remediated and merged to `v87`. See [CHANGELOG.md](CHANGELOG.md) for what shipped and [docs/technical/roadmap.md](docs/technical/roadmap.md) for current open work (none, as of closure).

---

## Orientation

A creator-led Django **project generator** (`quickscale plan` → `quickscale apply`) plus ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated apps via git subtree and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core`.

**Deployment context.** Generated apps run WSGI/Gunicorn, single Railway project, shared Postgres 18. No existing users; clean-break rule (no back-compat, no migration path). Development via parallel worktree tracks (`wt-track1/2/3`).

This file is reused as the template for the next structural autopsy — keep this section current, drop closed findings once remediated.
