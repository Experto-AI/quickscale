# Structural Autopsy: QuickScale

> **Status: In progress.** See [CHANGELOG.md](CHANGELOG.md) for resolved work and [docs/technical/roadmap.md](docs/technical/roadmap.md) for locked decisions.

---

## Orientation

A creator-led Django **project generator** (`quickscale plan` → `quickscale apply`) plus ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated apps via git subtree and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core`.

**Deployment context.** Generated apps run WSGI/Gunicorn, single Railway project, shared Postgres 18. No existing users; clean-break rule (no back-compat, no migration path). Development via parallel worktree tracks (`wt-track1/2/3`).

---

## Ranked findings

| # | Finding | Status |
|---|---------|--------|
| | | |

---

## Two independent clusters (summary)

_To be filled in after findings are ranked._
