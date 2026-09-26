# Beta Site Migration Playbook

A guide for keeping `experto-ai-web` and `bap-web` current with new QuickScale releases.

Trigger prompt for the maintainer command or report-assisted recovery:
> "I have a new quickscale project at `/tmp/xxxx`, incorporate the current web at `$HOME/current-web` — follow `docs/planning/beta-site-migration.md`"

## Current maintainer automation surface (updated for v0.89.0)

This playbook documents the beta-site-only maintainer workflow introduced in v0.81.0 and tightened in v0.89.0 for `experto-ai-web` and `bap-web`.

```bash
make beta-migrate-fresh DONOR=/abs/path/to/existing-beta-site RECIPIENT=/abs/path/to/fresh-scaffold
```

Rules for the current maintainer tool:
- `make beta-migrate-fresh` runs deterministic file mutation on the throwaway recipient and executes the local verification stack by default; add `DRY_RUN=1` to emit the plan/report without mutating files
- implemented in `quickscale_devtools.beta_migration`; `scripts/beta_migrate.py` is only the thin maintainer wrapper, not a QuickScale module or public `quickscale` CLI command
- reports which project's `settings/production.py`, `start.sh`, and `Dockerfile` form the effective runtime, rejects unresolved command settings or launcher/package skew before mutation, and keeps fresh-first `.quickscale/state.yml` identity metadata aligned with the reconciled scaffold
- a run that completes its verification stack writes `MIGRATION_PROMPT.md` into the recipient — what was migrated, every remaining manual action with its paths and governing rule, the hard constraints, and the done criteria — for a coding assistant to complete the remainder; dry runs and runs blocked before or during execution write no prompt
- `DONOR` and `RECIPIENT` are the only required operator inputs and must be provided explicitly on every run
- prefer deterministic Python transforms over bash-heavy pipelines
- if a step cannot be resolved safely, stop and emit a partial report with `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions` for a maintainer or AI coding assistant to continue
- the reference workflows below remain canonical for the current automation boundary and the manual continuation steps

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

`apply` generates the project in the directory named after the slug, and never writes
`quickscale.yml` itself: the file `plan` wrote is the only copy and the migration requires it in
the recipient root. So run `plan` without `-o` from a staging directory, `apply` from the
`<slug>` directory it creates, and move that whole directory to the target path:

```bash
STAGE=/home/victor/code/.bap-web-new.stage
RECIPIENT=/home/victor/code/bap-web-new
rm -rf "$STAGE" "$RECIPIENT" && mkdir -p "$STAGE" && cd "$STAGE"
quickscale plan bap-web        # writes bap-web/quickscale.yml; donor's theme and modules; no Docker
cd bap-web && quickscale apply --split-refs-from-branches
mv "$STAGE/bap-web" "$RECIPIENT" && rm -rf "$STAGE"
rm -rf "$RECIPIENT/.venv"      # a moved virtualenv keeps its old path; the verification stack reinstalls it
test -f "$RECIPIENT/quickscale.yml"
cd /home/victor/code/quickscale
make beta-migrate-fresh DONOR=/home/victor/code/bap-web RECIPIENT="$RECIPIENT"
```

Check the iteration by the run report, the remaining items in `$RECIPIENT/MIGRATION_PROMPT.md`,
and the donor's pytest and Vitest suites run in the recipient. Live-site Playwright and screenshot
parity run in the final iteration only. SA214 replaces this block with one non-interactive
`make beta-migrate-iterate` target.

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
The final iteration runs with every row closed.

| ID | Found in iteration | Gap | Kind | Resolution | Evidence | Status |
|---|---|---|---|---|---|---|
| G-001 | 0 (2026-09-26) | The fresh-first preflight blocks: donor `bap_web/settings/production.py` (generated on v0.62.0) predates the SA206 runtime settings facade and selects its database inline. The donor is read-only, so the block cannot be cleared on the donor side. | tool fix | The tool stops treating an old donor's `production.py` as authoritative: it ports only the donor's real customizations onto the recipient's generated, facade-based `production.py` (or rewrites the donor's database block onto the facade), and reports each carried customization. | — | open |

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

The donor-owned `settings/production.py` must call the versioned QuickScale runtime settings
facade (`from quickscale_core.runtime.settings import resolve_runtime_database_url`) instead of
carrying an inline copy of the command-mode contract; the facade declares the command allowlists
once. The preflight is a canonical-shape whitelist: the four inputs must be read through their
canonical forms (`config("RUNTIME_DATABASE_URL", default=None)`, `config("DATABASE_URL",
default=None)`, `os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND", "")`,
`os.environ.get("QUICKSCALE_NON_DB_COMMAND", "")`), passed to the facade call by name, and
`DATABASES["default"]` must parse the call's result — with no later statement superseding it.
Every use of `QUICKSCALE_PRIVILEGED_COMMAND` or `QUICKSCALE_NON_DB_COMMAND` in the effective
launchers must use a supported static assignment form. Computed, continued, concatenated, unknown, or otherwise
unresolved values, persistent Docker `ENV` assignments, mismatched `manage.py` arguments, and
privileged commands that do not blank `RUNTIME_DATABASE_URL` block the workflow before any project
file changes. Unguarded `manage.py` invocations of commands covered by those allowlists also block;
the generated required command set must remain complete, and the effective Dockerfile must retain
exactly one canonical `CMD ["./start.sh"]` runtime entrypoint.

---

## Reference workflow — fresh-first approach

### Inputs

```
DONOR     = path to the existing beta site         (e.g. ~/Code/experto-ai-web)
RECIPIENT = path to the fresh QuickScale scaffold  (e.g. /tmp/test80)
```

The RECIPIENT must already exist — run `quickscale plan <slug> && quickscale apply` to create it.
**Best practice: use the same slug as the existing project** (`experto-ai-web`, `bap-web`) to avoid
package name substitutions in transplanted Django files.

Set both variables explicitly for the shipped command. The command is the sole
executable mutation workflow in this section; the phase snippets below document
its implementation for report-based recovery and must not be rerun after a
successful command.

---

### Executor phase 0 — Derive variables (reference only)

Do not run this snippet before or after the command. It documents how the
executor resolves identity fields from the two required paths.

```python
import tomllib, yaml, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml", "rb") as f:
    d_toml = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f:
    r_toml = tomllib.load(f)

DONOR_PKG = d_toml["tool"]["poetry"]["packages"][0]["include"]  # e.g. "experto_ai_web"
RECIPIENT_PKG = r_toml["tool"]["poetry"]["packages"][0]["include"]  # e.g. "test80"

with open(f"{DONOR}/quickscale.yml") as f:
    d_qs = yaml.safe_load(f)
with open(f"{RECIPIENT}/quickscale.yml") as f:
    r_qs = yaml.safe_load(f)

DONOR_SLUG = d_qs["project"]["slug"]  # e.g. "experto-ai-web"
RECIPIENT_SLUG = r_qs["project"]["slug"]  # e.g. "test80"

SAME_IDENTITY = (
    DONOR_PKG == RECIPIENT_PKG and DONOR_SLUG == RECIPIENT_SLUG
)  # package and slug are separate identity fields
```

---

### Step 1 — Run the shipped fresh-first migration

If the fresh scaffold has a different package or slug, let the shipped maintainer command perform
the identity reconciliation. Package and slug are separate fields even when the source scaffold
uses the same one-word token for both (for example, `test80`). A global `sed` replacement cannot
distinguish those meanings and is not a safe fallback.

```bash
make beta-migrate-fresh DONOR="$DONOR" RECIPIENT="$RECIPIENT"
```

**Do not rerun executor phases 2–8 after Step 1.** The command already performs
identity reconciliation, frontend and Django copies, path-dependency sync, and
the complete local verification stack. Those phases are non-executable reference
for reviewing the report or resuming from its last completed deterministic step.
Steps 9–10 are the remaining operator actions.

If an agent must resume from a partial report after this step, it must preserve the same
path-specific semantics as the executor:

- update `quickscale.yml`'s `project.slug` and `project.package` as structured fields, then rename
  the Django package directory
- require an existing `.quickscale/state.yml` identity to match the recipient before mutation, then
  update its project slug/package and package-prefixed `managed_files` keys under the state advisory lock
- write the donor slug to `[tool.poetry].name`, but use the donor package for Poetry's package
  include, Django settings references, coverage source, and django-stubs settings
- reconcile every generated identity-bearing recipient file, including
  package-init docstrings, `.env*`, `db/init.sql`, generated docs/templates/tests,
  CI/lint commands, and `frontend/package.json`, without transferring structural
  ownership from the fresh scaffold
- replace derived package values as units (`<package>_app`,
  `<package>_app_password`, and `<package>-frontend`) before raw package tokens
- in `docker-compose.yml`, use slug semantics for container names, resource labels,
  and default image names; use package semantics for Django settings, database
  names, and runtime role/password references
- use slug semantics for any legacy baked identity in `frontend/src/hooks/useModules.ts`; current
  post-SA106 hooks are project-agnostic, so this is normally a no-op

After reconciliation, treat `RECIPIENT_PKG` as `DONOR_PKG` and `RECIPIENT_SLUG` as `DONOR_SLUG`
for the remaining steps.

---

### Executor phase 2 — Transplant App.tsx (reference only)

The existing project's `App.tsx` is the custom SPA router — replace the scaffold's default version.
The fresh recipient's `useModules.ts` is already project-agnostic per SA106 (no baked/default
projectName or embedded project slug; runtime identity flows from
`window.__QUICKSCALE__.projectName`), so only the custom router is transplanted here.

```bash
cp "$DONOR/frontend/src/App.tsx" "$RECIPIENT/frontend/src/App.tsx"
```

---

### Executor phase 3 — Transplant custom pages (reference only)

Copy only pages that exist in the existing project (DONOR) but NOT in the fresh scaffold (RECIPIENT).
These are the truly custom pages (Home, About, Services, CaseStudies, Properties, etc.).
Pages that already exist in the RECIPIENT (fresh scaffold pages like Dashboard, BlogPage, etc.) are
kept as-is — they are newer and should not be overwritten.

```python
import shutil, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

donor_pages = set(os.listdir(f"{DONOR}/frontend/src/pages"))
recipient_pages = set(os.listdir(f"{RECIPIENT}/frontend/src/pages"))

custom_only = donor_pages - recipient_pages  # pages only in the existing project

for page in sorted(custom_only):
    src = f"{DONOR}/frontend/src/pages/{page}"
    dst = f"{RECIPIENT}/frontend/src/pages/{page}"
    shutil.copy(src, dst)
    print(f"Copied page: {page}")
```

---

### Executor phase 4 — Transplant custom component directories (reference only)

Copy all component directories from the existing project EXCEPT `ui/` (keep the fresh scaffold's
shadcn components). Overwrite any same-named dirs in the RECIPIENT — the existing project's
`layout/`, `home/`, `shared/` etc. contain the real custom content.
New module component dirs in RECIPIENT that don't exist in DONOR (`social/`, `forms/`) are preserved.

```python
import shutil, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

donor_dirs = set(os.listdir(f"{DONOR}/frontend/src/components"))
SKIP = {"ui"}  # always keep recipient's fresh shadcn ui components

for d in sorted(donor_dirs - SKIP):
    src = f"{DONOR}/frontend/src/components/{d}"
    dst = f"{RECIPIENT}/frontend/src/components/{d}"
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"Copied component dir: {d}/")
```

---

### Executor phase 5 — Transplant src utilities (reference only)

Copy static assets, data, types, and stores from the existing project if they exist.
The fresh scaffold may not have these directories at all.

```bash
for dir in assets data types stores; do
    if [ -d "$DONOR/frontend/src/$dir" ]; then
        rm -rf "$RECIPIENT/frontend/src/$dir"
        cp -r  "$DONOR/frontend/src/$dir" "$RECIPIENT/frontend/src/$dir"
        echo "Copied: frontend/src/$dir/"
    fi
done
```

---

### Executor phase 6 — Transplant custom Django files (reference only)

Copy the existing project's hand-written Django files into the RECIPIENT's package directory.
If slugs differ they were already fixed in Step 1, so `DONOR_PKG == RECIPIENT_PKG` at this point.

```python
import shutil, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]
DONOR_PKG = os.environ["DONOR_PKG"]  # already set equal to RECIPIENT_PKG

FILES = [
    "urls.py",  # custom URL routing (healthcheck, sitemap, SPA catch-all)
    "views.py",  # custom views (404, robots.txt)
    "middleware.py",  # custom middleware (experto-ai-web only)
    "sitemaps.py",  # sitemap definitions (experto-ai-web only)
    "context_processors.py",  # custom context processors
    "settings/production.py",  # production overrides
]

for f in FILES:
    src = f"{DONOR}/{DONOR_PKG}/{f}"
    dst = f"{RECIPIENT}/{DONOR_PKG}/{f}"
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
        print(f"Copied: {DONOR_PKG}/{f}")
    # else: file doesn't exist in donor (e.g. no middleware.py in bap-web) — skip silently
```

**Do NOT copy** from the existing project:
- `settings/modules.py` — auto-managed by `quickscale apply`; RECIPIENT's is correct
- `settings/base.py` — keep RECIPIENT's (it's the latest scaffold version)
- `settings/local.py` — keep RECIPIENT's (it uses the new scaffold patterns)
- `urls_modules.py` — auto-managed; RECIPIENT's is correct

---

### Executor phase 7 — Update pyproject.toml path dependencies (reference only)

The fresh scaffold's `pyproject.toml` already has the right non-module deps (updated versions,
`django-markdownx`, etc.). The only thing to add is path dependencies for any modules in the
existing project that the fresh scaffold doesn't have (if slugs were the same and the fresh
scaffold was generated with fewer modules).

This step transfers dependency metadata only; it never copies embedded module source. Every added
path dependency must already resolve to an existing directory inside the recipient (for example,
`modules/blog`). The shipped command blocks before mutation if a donor-only dependency would point
to a missing or external path. Regenerate the fresh scaffold with all desired modules, or embed the
missing module in the recipient through the supported QuickScale workflow, before retrying.

In the recommended case (same slug, fresh scaffold generated with all desired modules), this step
is a no-op. Run it anyway as a safety check.

```python
import tomllib, tomli_w, os
from pathlib import Path

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]
recipient_root = Path(RECIPIENT).resolve()

with open(f"{DONOR}/pyproject.toml", "rb") as f:
    d = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f:
    r = tomllib.load(f)

# Find path deps in donor that are missing from recipient
donor_paths = {
    k: v
    for k, v in d["tool"]["poetry"]["dependencies"].items()
    if isinstance(v, dict) and "path" in v
}
recipient_deps = r["tool"]["poetry"]["dependencies"]

# Fail closed exactly like the shipped command: every added path dependency
# must resolve to an existing directory inside the recipient.
for k, v in donor_paths.items():
    if k in recipient_deps:
        continue
    target = (recipient_root / v["path"]).resolve()
    if not target.is_relative_to(recipient_root) or not target.is_dir():
        raise SystemExit(
            f"Refusing to add {k}: {v['path']!r} does not resolve to an existing "
            f"directory inside {recipient_root}"
        )

added = []
for k, v in donor_paths.items():
    if k not in recipient_deps:
        recipient_deps[k] = v
        added.append(k)

if added:
    with open(f"{RECIPIENT}/pyproject.toml", "wb") as f:
        tomli_w.dump(r, f)
    print(f"Added missing path deps: {added}")
else:
    print("pyproject.toml path deps already complete — no changes needed")
```

---

### Executor phase 8 — Run migrations and verify (reference only)

```bash
cd "$RECIPIENT"

# Reinstall Python deps (pyproject.toml may have changed)
poetry lock && poetry install

# Install frontend deps
cd frontend && pnpm install && cd ..

# Build frontend — must succeed before testing
cd frontend && pnpm build && cd ..

# Apply all Django migrations (new modules from fresh scaffold)
quickscale manage migrate

# Run all tests
pytest
cd frontend && pnpm test && cd ..
```

---

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
EXISTING_REPO="$HOME/Code/experto-ai-web"   # the repo Railway is connected to

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
| `frontend/package.json` | keep RECIPIENT's |
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
| `media/`, `.env`, `poetry.lock` | never copy; the throwaway recipient's `.env` receives identity-only reconciliation for local verification and remains excluded from repo replacement |

---

## Strategy 2: Ongoing maintenance

Use this after the initial catch-up. The beta site is current — just keeping it there.

### 2a — Update existing module code

```bash
cd ~/Code/experto-ai-web
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
cd ~/Code/experto-ai-web
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

See [railway.md § Minimum environment variable contract](../deployment/railway.md#media-storage-on-railway) for the canonical env var list (S3 and R2 variants).

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
railway up --service experto-ai-web
```

### Confirm migrations ran

```bash
railway logs --service experto-ai-web --follow
# Expect lines like: Applying social.0001_initial... OK
```

### Rollback

```bash
# Railway dashboard: Deployments tab → previous deployment → Redeploy
railway redeploy <deployment-id> --service experto-ai-web
```

---

## Checklists

### Initial catch-up checklist

```
[ ] DONOR and RECIPIENT paths confirmed
[ ] Fresh-first throwaway recipient prepared
[ ] Fresh-first report confirms complete field-aware identity reconciliation, including authoritative `.quickscale/state.yml`, derived database/frontend values, and `start.sh`
[ ] Fresh-first report confirms App.tsx, custom pages/components, utilities, Django files, and missing path deps were copied
[ ] Tool report contains seven passed verification results: `poetry lock`, `poetry install`, `pnpm install`, `pnpm build`, `quickscale manage migrate`, `pytest`, and `pnpm test`
[ ] Local smoke-test completed — existing pages intact and new module pages work
[ ] Effective donor-owned production settings call `quickscale_core.runtime.settings.resolve_runtime_database_url` before the current maintainer tool is invoked
[ ] Result committed or staged in the target repo
[ ] Module env vars set in Railway (storage, notifications if added)
[ ] Merged to main and Railway deployment confirmed
[ ] Migrations visible in Railway logs
[ ] Production smoke-test passed
```

### Outstanding maintainer to-do (SA67, tracked outside roadmap.md)

Per `decisions.md §Beta-Site External Verification Scope`, verifying and
patching the *live* deployed state of `experto-ai-web`/`bap-web` is out of
scope for repo automation and any coding-agent session — no repository or
deployment access to either site exists from within this monorepo. This is a
manual maintainer action, not a roadmap.md checklist item:

```
[ ] experto-ai-web: diff deployed start.sh + settings/production.py against
    current templates; record Redis presence for deployment history and reconcile
    SA63/SA68's complete env-pair bridge before invoking the current maintainer tool
[ ] bap-web: same check
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

## SA68 rollout closeout notes

Findings from the completed SA68 work (the migrate-path launcher env-pair contract, completing Finding 6's Option 1).

### Delivered contract

The final design uses two explicit one-shot command env vars — `QUICKSCALE_PRIVILEGED_COMMAND` and `QUICKSCALE_NON_DB_COMMAND` — instead of the earlier single-flag/argv-sniffing idiom. All three argv deciders (`start.sh.j2`'s migrate-line env gap, `production.py.j2`'s `elif "migrate" in sys.argv` branch, `orgs/apps.py`'s `_is_migrate_command()`) are deleted. Every launcher command now routes through the same env-pair bridge.

### Historical rollout ordering (superseded for current automation)

The Redis-dependent launcher-first sequence used during SA63/SA68 delivery is
historical deployment context, not a compatibility path accepted by the current
maintainer tool. The tool now requires the effective donor-owned
`settings/production.py` to call the `quickscale_core.runtime.settings` facade
(`resolve_runtime_database_url`) before the migration starts, regardless of
whether `REDIS_URL` is set.

A pre-SA68 production settings file that still uses the former
`"migrate" in sys.argv` branch is therefore incompatible with the current
command. Reconcile that donor-owned file first by importing and calling the
runtime settings facade while preserving its unrelated site configuration;
do not replace it wholesale. Commit and verify that facade adoption before
invoking `make beta-migrate-fresh`. Do not use
Redis presence to justify a launcher-first run of the current automation.

### Non-blocking validation findings preserved

- **Orgs module test context:** Orgs module tests require module-local pytest context for direct module runs (not triggered from the root `pytest`). This is a test-tooling affordance, not a gap.
- **Runtime smoke e2e:** The runtime smoke e2e tests remain explicitly marked (`pytest -m e2e`) and opt-in. They are not part of the default `make test` run.

## AI assistant continuation guide

Use this when the maintainer tool is only partially implemented or stops before local verification completes.

1. Read this playbook, the current [v0.89.0 release note](../releases/release-v0.89.0.md), and the historical [v0.81.0 tooling note](../releases/release-v0.81.0.md) before changing the automation behavior.
2. Treat the provided `DONOR` and `RECIPIENT` values as authoritative rather than inferring roles from directory names.
3. Resume from the last completed deterministic step in the tool's report — and from `MIGRATION_PROMPT.md` in the recipient after a completed run — instead of rerunning earlier destructive steps.
4. Fresh-first continuation order: field-aware identity fix (including locked authoritative state reconciliation and `start.sh`) → frontend copies → Django file copies → path dependencies → local verification → manual repo handoff.
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
