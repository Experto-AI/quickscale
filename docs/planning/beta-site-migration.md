# Beta Site Migration Playbook

A guide for keeping `bap-web` current with new QuickScale releases.

Trigger prompt for the maintainer command or report-assisted recovery:
> "I have a new quickscale project at `/tmp/xxxx`, incorporate the current web at `$HOME/current-web` — follow `docs/planning/beta-site-migration.md`"

## Maintainer automation surface

This playbook documents the beta-site-only maintainer workflow for `bap-web`.

```bash
make beta-migrate-fresh DONOR=/abs/path/to/existing-beta-site RECIPIENT=/abs/path/to/fresh-scaffold
make beta-migrate-iterate DONOR=/abs/path/to/existing-beta-site RECIPIENT=/abs/path/to/throwaway-recipient
```

Rules for the current maintainer tool:
- `make beta-migrate-fresh` runs deterministic file mutation on the throwaway recipient and executes the local verification stack by default; add `DRY_RUN=1` to emit the plan/report without mutating files
- before any mutation every donor file is classified — generated-untouched, generated-customized, project-owned, module-edited, or build artifact — and a donor file that matches no class blocks the run and is named in the report
- project-owned Django apps beside `manage.py` are detected, copied without their donor migrations, registered in the recipient's user-owned `settings/base.py`, URL-mounted through the recipient's user-owned `urls.py`, and their model state is regenerated against the current released models before `migrate` runs; a donor migration operation the autodetector cannot reproduce (for example a FORCE-RLS `RunSQL` or a data `RunPython`) is carried into an appended migration after the regenerated initial state, and an operation that cannot be carried safely (unresolved reference, dynamic `operations` declaration, or another app's migration in its dependencies) blocks the run and is named instead of being dropped silently; donor-added frontend dependencies are merged into the recipient's `frontend/package.json`, keeping the recipient's version and reporting every conflict
- a recognized pre-facade donor `settings/production.py` is not refused and not copied raw: the tool rewrites only its inline database/command-selection block onto `quickscale_core.runtime.settings.resolve_runtime_database_url`, reusing the donor's canonical read names, and carries every other donor setting unchanged, naming the rewritten line span and each carried setting in the report; unrecognized shapes are still refused before mutation
- `make beta-migrate-iterate` runs one migration iteration: it reads slug, package, theme, and modules from the donor's `quickscale.yml`, regenerates the throwaway recipient through a staging directory and `quickscale apply --split-refs-from-branches`, then runs the fresh-first workflow against it; `DRY_RUN=1` plans the regeneration only
- implemented in `quickscale_devtools.beta_migration`; `scripts/beta_migrate.py` is only the thin maintainer wrapper, not a QuickScale module or public `quickscale` CLI command
- reports which project's `settings/production.py`, `start.sh`, and `Dockerfile` form the effective runtime, rejects unresolved command settings or launcher/package skew before mutation, and keeps fresh-first `.quickscale/state.yml` identity metadata aligned with the reconciled scaffold
- a run that completes its verification stack writes `MIGRATION_PROMPT.md` into the recipient — what was migrated, every remaining manual action with its paths and governing rule, the hard constraints, and the done criteria — for a coding assistant to complete the remainder; dry runs and runs blocked before or during execution write no prompt
- the completed prompt names every unresolved gap the run recorded, in the remaining-work form the prompt-driven port reads: the recorded pre-port surfaces and the donor's module divergences — stale copies the current module content supersedes, and real local edits to upstream or re-express — each with its paths and governing rule; the [gap ledger](#gap-ledger) row vocabulary stays maintainer-side
- the tool starts the recipient's database service from a clean state with a reserved loopback publication before the database-backed verification command and stops it, with its throwaway volumes, after the verification stack even when a command fails; the migration runs in the recipient's own Poetry environment as the sanctioned privileged command because the generated production image compiles the pre-port frontend sources in its build, and the database service is the project's own Compose definition; host-run `poetry run pytest` reads the recipient `.env` and needs the operator's PostgreSQL 18 service
- the verification environment inherits the project's own declarations — the non-live credential placeholders (the managed `.github/quickscale-ci-env` file the current workflow loads, or an older project's CI test job) and the `.env.example` restricted runtime-role URL — with the operator's environment winning; a copied donor Django file keeps its own symbols and receives every generated top-level symbol it lacks plus the imports those symbols need; donor package-root modules the recipient lacks are copied in and never overwrite a module the recipient owns
- the verification contract records pre-port manual-port surfaces instead of blocking: a non-zero exit from `pnpm build`, `poetry run pytest`, or `pnpm test` is recorded as a failed result plus a remaining manual action carrying the command and its captured output, and the stack continues; `poetry lock`, `poetry install`, `pnpm install`, `makemigrations`, and `poetry run python manage.py migrate` stay blocking, and a timeout or launch failure blocks regardless; a completed run writes the handoff prompt naming each recorded surface
- `DONOR` and `RECIPIENT` are the only required operator inputs and must be provided explicitly on every run
- prefer deterministic Python transforms over bash-heavy pipelines
- if a step cannot be resolved safely, stop and emit a partial report with `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions` for a maintainer or AI coding assistant to continue
- the tool owns the fresh-first phases end to end; the remaining operator actions are local smoke testing and the repository/release handoff

## Working documents

The port's `MIGRATION_PROMPT.md` and `CUTOVER.md` live in the recipient repository
(`bap-web-new`), which the tool writes them into; this repository keeps no copies. The two-stage
upgrade path is drafted in [`migration-upgrade-path-draft.md`](migration-upgrade-path-draft.md).

---

## Running a migration iteration

One iteration regenerates the recipient from scratch, migrates the donor into it, checks the
result, and records every gap in the [gap ledger](#gap-ledger). The recipient is never hand-edited
between iterations; a gap is fixed in QuickScale and the next iteration picks the fix up.

### Before a release is published

Build the recipient from the unreleased checkout. Run every command from the QuickScale repo root
unless a step says otherwise.

```bash
make install                   # CLI + local quickscale-core wheelhouse at the checkout's VERSION
git tag X.Y.Z -m "vX.Y.Z: QuickScale X.Y.Z"  # local only — NEVER push: a pushed version tag starts PyPI publication
make publish-modules           # push current module code to the splits/<module>-module branches and every branch reports up to date
```

`make publish-modules` refuses to run unless `HEAD` carries the local `X.Y.Z` tag matching
`VERSION`, and it needs a clean working tree: commit or stash first. Each published module adds a
`--rejoin` merge commit, so afterwards re-point the tag with
`git tag -f X.Y.Z -m "vX.Y.Z: QuickScale X.Y.Z"`. Split tags are not sealed;
`apply --split-refs-from-branches` embeds from the branches.

### One iteration

`make beta-migrate-iterate DONOR=/home/victor/code/bap-web RECIPIENT=/home/victor/code/bap-web-new`
is the one non-interactive iteration procedure. It reads slug, package, theme, and modules from the
donor's `quickscale.yml`, regenerates the throwaway recipient through a staging directory and
`quickscale apply --split-refs-from-branches`, then runs the fresh-first workflow against it.
`DRY_RUN=1` plans the regeneration only. The recipient is never hand-edited between iterations.

The iteration runs under the repository's Poetry environment, whose `quickscale` shadows the
installed CLI, so an unreleased target version resolves its lockstep `quickscale-core` pin only
through the wheelhouse `make install` staged:

```bash
export QUICKSCALE_LOCAL_WHEELHOUSE="$(readlink -f ~/.local/share/quickscale/current)/quickscale_wheels"
```

Host-run `poetry run pytest` reads the recipient `.env` and needs a PostgreSQL 18 service on
`localhost:5432`.

Check the iteration by the run report, the remaining items in `$RECIPIENT/MIGRATION_PROMPT.md`,
and the donor's pytest and Vitest suites run in the recipient. A recorded pre-port surface — a
failed `pnpm build`, `poetry run pytest`, or `pnpm test` that belongs to the donor's manual-port
work — appears as a failed verification result and a remaining action, not a blocker. Live-site
Playwright and screenshot parity run in the final iteration only.

### After a fix

| Fix lands in | Before the next iteration |
|---|---|
| migration tool, generator, theme, CLI | `make install` |
| a module under `quickscale_modules/` | `make install`, commit, `git tag -f X.Y.Z -m "vX.Y.Z: QuickScale X.Y.Z"`, `make publish-modules` |
| playbook only | nothing |

### After the release

Sealed tags exist and the published CLI resolves them: drop `--split-refs-from-branches` and the
local tag steps, and repin the recipient to the release before cutover.

## Gap ledger

Every gap an iteration finds gets one row, and a row is closed only by the evidence it names.
The final iteration runs with every row closed. A completed run emits its unresolved gaps in
the recipient prompt's remaining-work form; the maintainer lifts the rows the iteration leaves
open into this table.

Open rows go in this table; closed rows are deleted (their evidence lives in git history). No row is open.

| ID | Found in iteration | Gap | Kind | Resolution | Evidence | Status |
|---|---|---|---|---|---|---|

- **ID** — `G-NNN`, never reused.
- **Kind** — `tool fix`, `playbook step`, `project decision`, or `upstream to module`.
- **Evidence** — a test name, commit, or iteration whose check shows the gap gone. A masked
  screenshot region or an adapted or excluded donor test is a `project decision` row that says why.
- **Status** — `open` or `closed`.

---

## One approach for a major catch-up

| Approach | Working directory | What gets copied | Use when |
|----------|------------------|-----------------|----------|
| **Fresh-first** | Fresh scaffold at `/tmp/xxxx` | Custom content from existing project → fresh scaffold | You want a clean starting point; infrastructure is correct from the start |

Fresh-first executes through local verification on a throwaway recipient. The fresh scaffold
already has a correct, up-to-date `Dockerfile`, `start.sh`, `pyproject.toml`, and frontend build
config with no merges required.

After the initial catch-up, use **ongoing maintenance** for all future updates.

## Deterministic automation boundary

- **Fresh-first** is the deterministic automation target. The shipped target mutates the throwaway recipient and runs local verification by default; final repo replacement, push, deploy, secret setup, and smoke approval remain explicit operator steps.
- The workflow must avoid copying `.git`, `media/`, `.env`, or `poetry.lock` between projects. Generate derived artifacts only in the active working tree when the workflow explicitly reaches that step.

The compatibility preflight uses these effective runtime sources while preserving donor precedence:

| Mode | `settings/production.py` | `start.sh` | `Dockerfile` |
|---|---|---|---|
| Fresh-first | donor | recipient | recipient |

The effective `settings/production.py` must select its database through the versioned QuickScale
runtime settings facade (`from quickscale_core.runtime.settings import resolve_runtime_database_url`);
the facade declares the command allowlists once. A donor file that already calls the facade is used
as-is; a recognized pre-facade file has only its inline database/command-selection block rewritten
onto the facade by the migration, with every other donor setting carried unchanged. The preflight is
a canonical-shape whitelist: the four inputs must be read through their canonical forms
(`config("RUNTIME_DATABASE_URL", default=None)`, `config("DATABASE_URL", default=None)`,
`os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND", "")`,
`os.environ.get("QUICKSCALE_NON_DB_COMMAND", "")`), passed to the facade call by name, and
`DATABASES["default"]` must parse the call's result — with no later statement superseding it. An
inline copy the rewrite does not recognize is refused before any mutation.
Every use of `QUICKSCALE_PRIVILEGED_COMMAND` or `QUICKSCALE_NON_DB_COMMAND` in the effective
launchers must use a supported static assignment form. Computed, continued, concatenated, unknown, or otherwise
unresolved values, persistent Docker `ENV` assignments, mismatched `manage.py` arguments, and
privileged commands that do not blank `RUNTIME_DATABASE_URL` block the workflow before any project
file changes. Unguarded `manage.py` invocations of commands covered by those allowlists also block;
the generated required command set must remain complete, and the effective Dockerfile must retain
exactly one canonical `CMD ["./start.sh"]` runtime entrypoint.

---

## Fresh-first workflow — owned by the tool

`make beta-migrate-fresh` is the sole executable mutation workflow; do not re-derive its phases by
hand. One run performs, in order:

1. field-aware identity reconciliation (including the locked authoritative `.quickscale/state.yml`
   and `start.sh`);
2. App.tsx and donor-only page copies, then component-directory and utility-directory transplant;
3. selected Django file copies; a copied donor file keeps the donor's symbols and gains every
   generated top-level symbol it lacks (with the imports those symbols need), donor package-root
   modules the recipient lacks are adopted, and a recognized pre-facade donor
   `settings/production.py` has only its inline database/command-selection block rewritten onto
   `quickscale_core.runtime.settings.resolve_runtime_database_url`, with every other donor setting
   carried unchanged and named in the report;
4. project-owned app copy, registration, URL mounting, and recipient-local `makemigrations`
   regeneration; operations the autodetector cannot reproduce are carried into appended migrations
   after the regenerated initial state, and an operation that cannot be carried safely blocks before
   mutation;
5. missing path-dependency sync and donor-only frontend dependency merge (the recipient's version
   wins on a conflict, and every conflict is reported);
6. the donor design port into the never-overwritten `frontend/design/` layer;
7. the local verification stack (`poetry lock`, `poetry install`, `pnpm install`, `pnpm build`,
   `makemigrations`, `poetry run python manage.py migrate`, `poetry run pytest`, `pnpm test`),
   with the recipient's database service started before the database-backed command and stopped
   after the stack; a non-zero exit from `pnpm build`, `poetry run pytest`, or `pnpm test` is
   recorded as a remaining manual action and the stack continues, while every other non-zero exit,
   timeout, or launch failure blocks.

A run that completes its verification stack writes `MIGRATION_PROMPT.md` into the recipient with
every remaining manual action, its paths, and the governing rule. Dry runs and blocked runs write
no prompt. A completed run whose only failures are recorded pre-port surfaces still writes the
prompt, and the prompt is the terminal state for a donor whose divergent frontend sources and
tests the manual port owns. The contract does not classify a pre-port command failure by cause: a
failure inside those commands is triaged from its captured output, so an environment failure there
is recorded rather than blocked and the operator must read the report.

If a run stops partial, resume from the report's last completed deterministic step
(`completed_steps`, `skipped_steps`, `changed_files`, `verification_results`) instead of rerunning
earlier file mutations. The two operator actions below remain after a successful run.

### Step 9 — Smoke-test locally

```bash
cd "$RECIPIENT"
quickscale up
# http://localhost:8000/                — existing project home page renders
# http://localhost:8000/admin/          — Django admin loads
# http://localhost:8000/social          — if social module present: link tree page
# http://localhost:8000/social/embeds   — if social module present: embeds page
# All custom routes from App.tsx work (About, Services, Properties, etc.)
# Django admin → all new module admin sections visible
```

---

### Step 10 — Push to the production git repo

The result is in the RECIPIENT directory (`/tmp/xxxx`). Railway is watching the existing project's
git repo. Copy the result there to deploy.

```bash
EXISTING_REPO="$HOME/Code/bap-web"   # the repo Railway is connected to

cd "$EXISTING_REPO"
git status   # stash or commit any pending work
git checkout -b migrate/fresh-scaffold

# Replace all tracked files with the fresh result (preserves git history)
rsync -a --delete \
    --exclude='.git' \
    --exclude='media/' \
    --exclude='.env' \
    --exclude='poetry.lock' \
    "$RECIPIENT/" ./

# Re-generate the lockfile in the existing repo context
poetry lock

git add -A
git commit -m "chore: rebuild on fresh qs scaffold ($(basename $RECIPIENT))"

# Push and deploy
git push origin migrate/fresh-scaffold
# Open PR → merge to main → Railway auto-deploys
```

---

## File classification reference

What happens to each file during the fresh-first workflow.

| File / directory | Disposition (DONOR=existing project) |
|-----------------|--------------------------------------|
| `Dockerfile` | keep RECIPIENT's (already correct) |
| `start.sh` | keep RECIPIENT's, fixing package refs during identity reconciliation |
| `docker-compose.yml` | keep RECIPIENT's |
| `.pre-commit-config.yaml` | keep RECIPIENT's |
| `frontend/vite.config.ts`, `tsconfig*.json` | keep RECIPIENT's |
| `frontend/src/hooks/useModules.ts` | keep RECIPIENT's — project-agnostic per SA106 (no baked identity; runtime from `window.__QUICKSCALE__`) |
| `frontend/src/main.tsx` | keep RECIPIENT's (byte-identical only among projects from the same theme version; legacy pre-SA107 or customized recipients must compare/review for boot-validation and public-surface-handoff parity — parity is not proven) |
| `pyproject.toml` | keep RECIPIENT's; add any missing path deps from donor |
| `frontend/package.json` | keep RECIPIENT's identity and scripts; merge donor-only `dependencies`/`devDependencies` and report every version conflict, keeping the recipient's version |
| `quickscale.yml` | keep RECIPIENT's (already has target modules) |
| `.quickscale/state.yml` | keep RECIPIENT's authoritative state; reconcile project identity and package-prefixed managed-file keys under the state lock |
| `<pkg>/settings/modules.py` | auto-generated — keep RECIPIENT's |
| `<pkg>/urls_modules.py` | auto-generated — keep RECIPIENT's |
| `railway.json` | auto-generated — keep RECIPIENT's |
| `modules/` | already embedded in RECIPIENT — keep |
| `frontend/src/App.tsx` | copy from donor (custom routing); shipped gated routes (React.lazy via SA105) guaranteed only for **fresh current-theme recipients**; legacy/customized recipients must review/reconcile App.tsx |
| `frontend/src/pages/` (custom) | copy pages only in DONOR (Home, About, etc.) |
| `frontend/src/pages/` (scaffold) | keep RECIPIENT's (fresher; all module pages already present as dormant files per SA105) |
| `frontend/src/components/` (custom) | copy from donor (home/, layout/, shared/, seo/, properties/) |
| `frontend/src/components/ui/` | keep RECIPIENT's (fresh shadcn) |
| `frontend/src/components/` (new modules) | keep RECIPIENT's (social/, forms/ — present as SA105 dormant files in fresh scaffold) |
| `frontend/src/assets/`, `data/`, `types/`, `stores/` | copy from donor |
| `<pkg>/urls.py`, `views.py`, `middleware.py`, `sitemaps.py`, `context_processors.py` | copy from donor |
| `<pkg>/settings/production.py` | copy from donor |
| `<pkg>/settings/base.py`, `local.py` | keep RECIPIENT's |
| `<project app>/` (beside `manage.py`) | detect, copy from donor without `migrations/`, register in `<pkg>/settings/base.py`, mount its `urls.py` in `<pkg>/urls.py`, regenerate migrations before `migrate` |
| `media/`, `.env`, `poetry.lock` | never copy; the throwaway recipient's `.env` receives identity-only reconciliation for local verification and remains excluded from repo replacement |

---

## Strategy 2: Ongoing maintenance

Use this after the initial catch-up. The beta site is current — just keeping it there.

### 2a — Update existing module code

```bash
cd ~/Code/bap-web
git checkout -b update/qs-v<version>
quickscale update              # pulls latest for all installed modules via git subtree
git diff HEAD                  # review changes to managed files
quickscale manage migrate      # apply any new migrations
pytest
cd frontend && pnpm test && cd ..
git add -A && git commit -m "chore: update quickscale modules to v<version>"
```

### 2b — Add a single new module

```bash
cd ~/Code/bap-web
git checkout -b feat/add-<module>

# 1. Add module to quickscale.yml under modules:
#    <module>: null
#    (or with config options — see module.yml in reference project)

quickscale apply               # embeds module, regenerates wiring
quickscale manage migrate

# 2. Fresh current-theme generations ship every module surface as dormant files (SA105) — no manual copy needed. If surfaces are missing, do not assume they exist; stop and handle manually first.
# 3. Add route in App.tsx if it's a dashboard page (not needed for public-surface pages; renderQuickScaleRoot() dispatches public-social surfaces after validateQuickScaleConfig() validates the seam)

pytest && cd frontend && pnpm test && cd ..
git add -A && git commit -m "feat: add <module> module"
```

## Module-specific environment variables

Set in Railway dashboard before deploying. Required only for the listed modules.

### `storage`

See [railway.md § Minimum environment variable contract](../deployment/railway-operations.md#media-storage-on-railway) for the canonical env var list (S3 and R2 variants).

### `notifications`

Deploy first, then open Django admin → Notification Settings and set the env var name fields
(defaults to `RESEND_API_KEY` and `RESEND_WEBHOOK_SECRET`). Then add to Railway:

```
RESEND_API_KEY=re_...
RESEND_WEBHOOK_SECRET=whsec_...
```

### `backups`

No env vars for local backups. For remote S3/R2 backups, configure via BackupPolicy admin.

### `social`

No env vars. Configure links and embeds via Django admin after migration.

---

## Railway deployment

### Before pushing — set env vars for new modules

```bash
# Set all in one batch to trigger only one Railway redeploy
railway variables --set \
  RESEND_API_KEY=re_... \
  RESEND_WEBHOOK_SECRET=whsec_... \
  --service bap-web
```

### Push and deploy

```bash
# Merge to main → Railway auto-deploys (recommended)
git push origin <branch-name>

# Or deploy directly:
railway up --service bap-web
```

### Confirm migrations ran

```bash
railway logs --service bap-web --follow
# Expect lines like: Applying social.0001_initial... OK
```

### Rollback

```bash
# Railway dashboard: Deployments tab → previous deployment → Redeploy
railway redeploy <deployment-id> --service bap-web
```

---

## Checklists

### Initial catch-up checklist

```
[ ] DONOR and RECIPIENT paths confirmed
[ ] Fresh-first throwaway recipient prepared
[ ] Fresh-first report confirms complete field-aware identity reconciliation, including authoritative `.quickscale/state.yml`, derived database/frontend values, and `start.sh`
[ ] Fresh-first report confirms App.tsx, custom pages/components, utilities, Django files, and missing path deps were copied
[ ] Tool report shows every blocking verification command passed (`poetry lock`, `poetry install`, `pnpm install`, `poetry run python manage.py migrate`) — plus a passed recipient-local `poetry run python manage.py makemigrations <app>` for every migrated model-bearing app; any `pnpm build`, `poetry run pytest`, or `pnpm test` failure is recorded as a remaining manual action instead of blocking
[ ] Local smoke-test completed — existing pages intact and new module pages work
[ ] Effective production settings select their database through `quickscale_core.runtime.settings.resolve_runtime_database_url` — already facade-based in the donor, or rewritten by the tool from a recognized pre-facade block while the donor stays read-only
[ ] Result committed or staged in the target repo
[ ] Module env vars set in Railway (storage, notifications if added)
[ ] Merged to main and Railway deployment confirmed
[ ] Migrations visible in Railway logs
[ ] Production smoke-test passed
```

### Manual maintainer check (outside repo automation)

Per `decisions.md §Beta-Site External Verification Scope`, verifying and
patching the *live* deployed state of `bap-web` is out of
scope for repo automation and any coding-agent session — no repository or
deployment access to the site exists from within this monorepo. This is a
manual maintainer action, not a roadmap.md checklist item:

```
[ ] bap-web: diff deployed start.sh + settings/production.py against
    current templates; record Redis presence for deployment history and reconcile
    SA63/SA68's complete env-pair bridge before invoking the current maintainer tool
[ ] Record the outcome here (date, Redis state, whether a patch was needed)
```

*(Not yet performed — no entry below. Add one after the next manual check.)*

### Ongoing maintenance checklist

```
[ ] Branch created
[ ] quickscale update ran (for module code updates)
[ ] quickscale apply ran (for new module additions)
[ ] quickscale manage migrate ran
[ ] Blog/crm/listings/forms/social dormant surfaces present (fresh current-theme generation ships them as SA105 dormant files); if any are missing, confirm/reconcile them before proceeding
[ ] pytest passes; pnpm test passes
[ ] Env vars set in Railway for any new modules
[ ] Merged to main; Railway deployment confirmed
```

## Pre-facade donor settings

The tool requires the effective `settings/production.py` to select its database through
`quickscale_core.runtime.settings.resolve_runtime_database_url`. A recognized pre-facade block
(including the old `"migrate" in sys.argv` branch) is rewritten onto the facade, and the rest of
the donor configuration is carried unchanged. An unrecognized shape is refused before mutation.
Redis presence never justifies a launcher-first run.

## AI assistant continuation guide

Use this when the maintainer tool is only partially implemented or stops before local verification completes.

1. Read this playbook, the current [v0.89.0 release note](../releases/release-v0.89.0.md), and the historical [v0.81.0 tooling note](../releases/release-v0.81.0.md) before changing the automation behavior.
2. Treat the provided `DONOR` and `RECIPIENT` values as authoritative rather than inferring roles from directory names.
3. Resume from the last completed deterministic step in the tool's report — and from `MIGRATION_PROMPT.md` in the recipient after a completed run — instead of rerunning earlier destructive steps.
4. Fresh-first continuation order: field-aware identity fix (including locked authoritative state reconciliation and `start.sh`) → frontend copies → Django file copies (a recognized pre-facade `settings/production.py` is rewritten onto the runtime settings facade) → project-owned app migration (copy, registration, URL mount, model-state regeneration, and the carry of non-regenerable migration operations) → path dependencies → frontend dependency merge → donor design port → local verification (including the recipient-local `makemigrations` for every migrated app) → manual repo handoff.
5. If a step would require guessing about module adoption, deploy timing, or secrets, stop, record the skipped work in `skipped_steps`, and leave the operator follow-up in `pending_manual_actions`.
6. The minimum handoff payload for partial automation is `mode`, `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions`.

---

## Keeping the reference project current

Before starting any migration, regenerate the reference project so it reflects the latest scaffold:

```bash
cd /tmp
rm -rf test80
quickscale plan test80
# Wizard: showcase_react, select ALL available modules
cd test80 && quickscale apply
```

---

## Troubleshooting

### `quickscale apply` reports "module already embedded"

The module directory exists in `modules/` but was missing from `quickscale.yml`. Add it and
re-run apply — it skips re-embedding and only updates the wiring files.

### `quickscale update` reports merge conflicts in `modules/<name>/`

Local edits exist in a module directory. Stash or commit first. To contribute the edits upstream:
`quickscale push --module <name>`.

### Frontend build fails after the fresh-first file-copy steps

A copied file imports something not yet present in the recipient. Read the build error message,
find the missing import in the donor's `frontend/src/`, and copy only that file.

### `tomli_w` not installed

```bash
pip install tomli-w
```

Or run the pyproject.toml path-dependency sync manually: add every donor
`path` dependency that is missing from the recipient and whose target already
exists inside the recipient, keep the recipient's fresher non-path dependency
versions, and leave the recipient's `[tool.pytest.ini_options]` block unchanged.

### Social pages return 404 on production

`quickscale apply` generates the Django URL for `/social` in `urls_modules.py`. Confirm it ran
and that `urls_modules.py` includes the social patterns. Redeploy after running apply.

### New module admin section missing after deployment

Migrations did not run. Check Railway deployment logs. Run manually if needed:

```bash
railway run --service <slug> python manage.py migrate
```

### Dockerfile build fails (PostgreSQL 18 client step)

Requires `python:3.14-slim-bookworm` (explicit Debian variant), not `python:3.14-slim`.
Verify the fresh scaffold still uses `python:3.14-slim-bookworm` before continuing.

### `django-markdownx` import error at startup

The blog module requires `django-markdownx`. Confirm the fresh scaffold already includes it before rerunning `poetry lock && poetry install`.
