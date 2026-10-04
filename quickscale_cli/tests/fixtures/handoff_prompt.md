# Beta migration handoff prompt

This recipient was produced by the fresh-first beta migration (`make beta-migrate-fresh`);
the deterministic file migration and local verification already ran. Complete the remaining
work below, then hand the recipient back to the maintainer.

- Mode: fresh-first
- Phase: fresh-first-executed
- Donor: <DONOR>
- Identity reconciliation: not required
- Runtime provenance: settings/production.py=donor, start.sh=recipient, Dockerfile=recipient
- Verification: 7 passed, 0 failed

## What was migrated

Steps completed:
- parse-cli-arguments
- run-preflight-validations
- validate-fresh-first-runtime-files
- load-project-identities-and-diffs
- build-planned-actions
- identity-reconciliation
- copy-custom-router-and-pages
- copy-custom-components-and-utilities
- copy-selected-django-files
- copy-project-owned-apps
- register-and-mount-project-owned-apps
- sync-missing-path-dependencies
- merge-frontend-dependencies
- preserve-managed-recipient-files
- run-verification-stack

Recipient paths changed (11):
- `bap_web/context_processors.py`
- `bap_web/middleware.py`
- `bap_web/settings/production.py`
- `bap_web/sitemaps.py`
- `bap_web/urls.py`
- `bap_web/views.py`
- `frontend/src/App.tsx`
- `frontend/src/assets`
- `frontend/src/components/layout`
- `frontend/src/pages/About.tsx`
- `pyproject.toml`

Diff summary:
- Module diff: donor-only=['social'], recipient-only=['(none)']
- Path dependency diff: donor-only=['quickscale-module-social'], recipient-only=['(none)']
- Frontend dependency merge: donor-only=['(none)'], version conflicts=['(none)']

Verification commands:
- `poetry lock` — passed
- `poetry install` — passed
- `pnpm install` — passed
- `pnpm build` — passed
- `quickscale manage migrate` — passed
- `pytest` — passed
- `pnpm test` — passed

## Remaining work

- [ ] `run-local-smoke-checks` — Start the verified recipient, confirm the home page, admin, custom routes, and any installed public module pages.
      Paths: `.`
      Rule: Smoke-check every surface the live site serves before replacing any repository.
- [ ] `replace-existing-repository` — Copy the verified recipient into the real beta-site repository while excluding .git, media, .env, and poetry.lock.
      Paths: `.`
      Rule: Never copy `.git`, `media/`, `.env`, or `poetry.lock` between the donor and the real repository.
- [ ] `create-pr-and-merge` — Commit in the real repository, open a PR, review the diff, and merge after approval.
      Paths: `.`
      Rule: Merge exactly the reviewed and verified recipient; do not hand-edit past the reviewed tip.
- [ ] `set-module-env-vars` — Configure any required Railway environment variables for newly adopted modules without storing secret values in the report.
      Paths: `modules/auth`
      Rule: Set only the modules' declared environment variables; never store secret values in the report or the repository.
- [ ] `deploy-and-verify` — Deploy through the existing repo workflow, confirm migrations in logs, and run production smoke checks.
      Paths: `.`
      Rule: Confirm the deployment logs show the migrations applying before running production smoke checks.
- [ ] `keep-rollback-reference` — Keep the previous git and Railway deployment reference available until the new release is validated.
      Paths: (none)
      Rule: Retain the previous git and Railway deployment reference until the reseeded site is verified.

## Hard constraints

- Keep the donor project read-only; every change lands in the recipient.
- Never copy `.git`, `media/`, `.env`, or `poetry.lock` between the two trees.
- Do not hand-patch QuickScale-managed files such as `settings/modules.py`, `urls_modules.py`, and the generated wiring; regenerate them through the supported QuickScale workflow.
- In-place edits under vendored module source (`modules/<name>/`) are outside the extension contract: upstream them into the module or re-express them as project-owned code before the recipient is handed over.
- The migration merged the donor's declared frontend dependencies and reported every version conflict; keep the recipient's declared versions and add no dependency it does not already declare.

## Done criteria

- The recipient's `pytest` suite and frontend `pnpm test` suite pass.
- Local smoke checks pass for the home page, Django admin, custom routes, and any installed public module pages.
- Every remaining item above is completed and recorded in the migration ledger.
- The verified recipient is committed in the real repository and merged through review, with the deploy confirming migrations.
