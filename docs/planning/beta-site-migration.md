# Beta Site Migration Playbook

A guide for keeping `experto-ai-web` and `bap-web` current with new QuickScale releases.

Trigger prompt for the maintainer command or report-assisted recovery:
> "I have a new quickscale project at `/tmp/xxxx`, incorporate the current web at `$HOME/current-web` — follow `docs/planning/beta-site-migration.md`"

## Current maintainer automation surface (updated for v0.89.0)

This playbook documents the beta-site-only maintainer workflow introduced in v0.81.0 and tightened in v0.89.0 for `experto-ai-web` and `bap-web`.

```bash
make beta-migrate-fresh DONOR=/abs/path/to/existing-beta-site RECIPIENT=/abs/path/to/fresh-scaffold
make beta-migrate-in-place DONOR=/abs/path/to/fresh-scaffold RECIPIENT=/abs/path/to/existing-beta-site
```

Rules for the current maintainer tool:
- `make beta-migrate-fresh` runs deterministic file mutation on the throwaway recipient and executes the local verification stack by default; add `DRY_RUN=1` to emit the plan/report without mutating files
- `make beta-migrate-in-place` emits the structured pre-apply checkpoint report by default; add `CONTINUE=1` or `--continue-after-checkpoint` to continue through the deterministic in-place copy/apply/verification sequence
- implemented in `quickscale_devtools.beta_migration`; `scripts/beta_migrate.py` is only the thin maintainer wrapper, not a QuickScale module or public `quickscale` CLI command
- reports which project's `settings/production.py`, `start.sh`, and `Dockerfile` form the effective runtime, rejects unresolved command settings or launcher/package skew before mutation, and keeps fresh-first `.quickscale/state.yml` identity metadata aligned with the reconciled scaffold
- `DONOR` and `RECIPIENT` are the only required operator inputs and must be provided explicitly on every run
- prefer deterministic Python transforms over bash-heavy pipelines
- if a step cannot be resolved safely, stop and emit a partial report with `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions` for a maintainer or AI coding assistant to continue
- the reference workflows below remain canonical for the current automation boundary and the manual continuation steps

---

## Two approaches for a major catch-up

| Approach | Working directory | What gets copied | Use when |
|----------|------------------|-----------------|----------|
| **Fresh-first (primary)** | Fresh scaffold at `/tmp/xxxx` | Custom content from existing project → fresh scaffold | You want a clean starting point; infrastructure is correct from the start |
| **In-place (alternative)** | Existing project at `$HOME/current-web` | Infrastructure files from a fresh scaffold → existing project | You want to stay in the existing git repo and not move files |

Both approaches can get you to the same end result, but the shipped automation is intentionally split: fresh-first executes through local verification on a throwaway recipient, while in-place remains checkpoint-first unless maintainers explicitly opt into the continuation path. The fresh-first approach is recommended because the fresh scaffold already has a correct, up-to-date `Dockerfile`, `start.sh`, `pyproject.toml`, and frontend build config with no merges required.

After the initial catch-up, use **ongoing maintenance** for all future updates.

## Deterministic automation boundary

- **Fresh-first** is the primary deterministic automation target. The shipped target mutates the throwaway recipient and runs local verification by default; final repo replacement, push, deploy, secret setup, and smoke approval remain explicit operator steps.
- **In-place** is checkpoint-first by default. The shipped target resolves identities and diffs, enforces clean-git preflight, and emits the explicit pre-apply review checkpoint; an explicit continuation opt-in then runs deterministic infrastructure copy, config merge, `quickscale apply`, post-apply adoption of only missing forms/social module-owned surfaces, and local verification. For **fresh current-theme recipients** (generated post-SA105), all module React pages (blog, crm, listings, forms, social) are unconditionally present as SA105 dormant files from generation — no adoption or copy steps needed. For **legacy pre-SA105 recipients**, there is no retroactive dormant-file guarantee for any module surface; blog/crm/listings/forms/social may all be absent before the continuation runs. The shipped continuation does **not** guarantee or backfill blog/crm/listings — running `quickscale apply` in a legacy user-owned frontend does not reliably produce them. The post-apply adoption copies only missing forms/social module-owned surfaces and preserves existing destinations. If blog/crm/listings surfaces are missing after the continuation completes, the maintainer must stop, record the compatibility gap, and restore/reconcile them manually before continuing. Recipient-owned `App.tsx` (review manually when newly added modules need dashboard routing changes — `App.tsx` gates ordinary module routes; public-social dispatch is handled by `renderQuickScaleRoot()` after `validateQuickScaleConfig()` validates the seam fail-hard). For fresh current-theme recipients, `main.tsx` is byte-identical and needs no special patch; legacy pre-SA107 or customized recipients must compare/review `main.tsx` because parity of boot validation and public-surface handoff is not proven. Smoke checks, env vars, PR merge, deploy, and rollback remain manual.
- **Both paths** must avoid copying `.git`, `media/`, `.env`, or `poetry.lock` between projects. Generate derived artifacts only in the active working tree when the workflow explicitly reaches that step.

The compatibility preflight uses these effective runtime sources while preserving donor precedence:

| Mode | `settings/production.py` | `start.sh` | `Dockerfile` |
|---|---|---|---|
| Fresh-first | donor | recipient | recipient |
| In-place | recipient | donor | donor |

Both command allowlists must be immutable literal `frozenset(...)` definitions. Every use of
`QUICKSCALE_PRIVILEGED_COMMAND` or `QUICKSCALE_NON_DB_COMMAND` in the effective launchers must use
a supported static assignment form. Computed, continued, concatenated, unknown, or otherwise
unresolved values, persistent Docker `ENV` assignments, mismatched `manage.py` arguments, and
privileged commands that do not blank `RUNTIME_DATABASE_URL` block the workflow before any project
file changes. Unguarded `manage.py` invocations of commands covered by those allowlists also block;
the generated required command set must remain complete, and the effective Dockerfile must retain
exactly one canonical `CMD ["./start.sh"]` runtime entrypoint.

---

## Reference workflow — fresh-first approach (primary)

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

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

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

## Reference workflow — in-place alternative

Use this when you prefer to stay in the existing git repo without copying files to a temp location.

Current tooling boundary: `make beta-migrate-in-place ...` emits the checkpoint report by default. Add `CONTINUE=1` or `--continue-after-checkpoint` to continue through the deterministic infrastructure copy, config merge, `quickscale apply`, post-apply adoption of only missing forms/social module-owned surfaces, and local verification steps below. For **fresh current-theme recipients** (generated post-SA105), all module React pages (blog, crm, listings, forms, social) are unconditionally present as SA105 dormant files from generation — no adoption or copy steps needed. For **legacy pre-SA105 recipients**, there is no retroactive dormant-file guarantee for any module surface; blog/crm/listings/forms/social may all be absent before the continuation runs. The shipped continuation does **not** guarantee or backfill blog/crm/listings — running `quickscale apply` in a legacy user-owned frontend does not reliably produce them. The post-apply adoption copies only missing forms/social module-owned surfaces and preserves existing destinations. If blog/crm/listings surfaces are missing after the continuation completes, the maintainer must stop, record the compatibility gap, and restore/reconcile them manually before continuing. Recipient-owned `App.tsx` (review manually when newly added modules need dashboard routing changes — `App.tsx` gates ordinary module routes; public-social dispatch is handled by `renderQuickScaleRoot()` after `validateQuickScaleConfig()` validates the seam fail-hard). For fresh current-theme recipients, `main.tsx` is byte-identical and needs no special patch; legacy pre-SA107 or customized recipients must compare/review `main.tsx` because parity of boot validation and public-surface handoff is not proven. Smoke tests, env var setup, PR merge, deploy, and rollback remain manual even after continuation succeeds.

### Inputs

```
DONOR     = path to the fresh QuickScale scaffold  (e.g. /tmp/test80)
RECIPIENT = path to the existing beta site         (e.g. ~/Code/experto-ai-web)
```

The fresh scaffold is used only as a source of infrastructure files. The existing project's
custom content (pages, components, Django files) stays in place throughout.

Set both variables explicitly before running the supported commands. The scaffold
path is a required donor input rather than a fallback location. The only
supported mutation path is the checkpoint plus explicit continuation shown in
Step 1; phases 2–7 are implementation reference and must not be executed
separately after the continuation.

---

### Executor phase 0 — Derive variables (reference only)

Do not run this snippet separately. The checkpoint command derives these values
and records them in its report.

```python
import tomllib, yaml, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml", "rb") as f:
    d_toml = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f:
    r_toml = tomllib.load(f)

DONOR_PKG = d_toml["tool"]["poetry"]["packages"][0]["include"]  # e.g. "test80"
RECIPIENT_PKG = r_toml["tool"]["poetry"]["packages"][0]["include"]  # e.g. "experto_ai_web"

with open(f"{DONOR}/quickscale.yml") as f:
    d_qs = yaml.safe_load(f)
with open(f"{RECIPIENT}/quickscale.yml") as f:
    r_qs = yaml.safe_load(f)

DONOR_SLUG = d_qs["project"]["slug"]
RECIPIENT_SLUG = r_qs["project"]["slug"]

NEW_MODULES = set(d_qs["modules"].keys()) - set(r_qs["modules"].keys())
```

---

### Step 1 — Create migration branch

```bash
cd "$RECIPIENT"
git status   # must be clean; stash if not
git checkout -b migrate/$(basename "$DONOR")

# Emit and review the non-mutating checkpoint report.
make beta-migrate-in-place DONOR="$DONOR" RECIPIENT="$RECIPIENT"

# After review, run the one supported deterministic continuation.
make beta-migrate-in-place DONOR="$DONOR" RECIPIENT="$RECIPIENT" CONTINUE=1
```

The continuation performs phases 2–7 once. If it stops, resume only from the
last completed deterministic step named in the report; never restart the copy
sequence against a partially changed recipient.

---

### Executor phase 2 — Copy infrastructure files (reference only)

```bash
cp "$DONOR/Dockerfile" "$RECIPIENT/Dockerfile"
cp "$DONOR/start.sh" "$RECIPIENT/start.sh"

cp "$DONOR/docker-compose.yml" "$RECIPIENT/docker-compose.yml"

for f in .pre-commit-config.yaml frontend/vite.config.ts \
          frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json \
          frontend/eslint.config.js frontend/postcss.config.js frontend/prettier.config.js \
          frontend/src/hooks/useModules.ts frontend/src/lib/validateQuickScaleSeam.ts; do
    [ -f "$DONOR/$f" ] && cp "$DONOR/$f" "$RECIPIENT/$f"
done
```

The shipped continuation then applies package-only substitution to `Dockerfile` and `start.sh`,
slug/package field semantics to `docker-compose.yml`, and slug-only substitution to any legacy
baked identity in `frontend/src/hooks/useModules.ts`. Do not replace donor package and slug tokens
globally: a scaffold such as `test80` can use the same source token for both fields while the
recipient uses different values such as `experto-ai-web` and `experto_ai_web`.

---

### Executor phase 3 — Merge pyproject.toml (reference only)

Keep the recipient's module path dependencies and pytest settings; merge in the donor's non-path dependency versions only.

```python
import tomllib, tomli_w, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml", "rb") as f:
    d = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f:
    r = tomllib.load(f)

module_paths = {
    k: v
    for k, v in r["tool"]["poetry"]["dependencies"].items()
    if isinstance(v, dict) and "path" in v
}
non_paths = {
    k: v
    for k, v in d["tool"]["poetry"]["dependencies"].items()
    if not (isinstance(v, dict) and "path" in v)
}
r["tool"]["poetry"]["dependencies"] = {**non_paths, **module_paths}

# Keep the recipient's [tool.pytest.ini_options] block exactly as-is.

with open(f"{RECIPIENT}/pyproject.toml", "wb") as f:
    tomli_w.dump(r, f)
```

---

### Executor phase 4 — Merge frontend/package.json (reference only)

```python
import json, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/frontend/package.json") as f:
    d = json.load(f)
with open(f"{RECIPIENT}/frontend/package.json") as f:
    r = json.load(f)

merged = {**d, "name": r["name"]}

with open(f"{RECIPIENT}/frontend/package.json", "w") as f:
    json.dump(merged, f, indent=2)
    f.write("\n")
```

---

### Executor phase 5 — Update quickscale.yml and run apply (reference only)

```python
import yaml, os

DONOR = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/quickscale.yml") as f:
    d = yaml.safe_load(f)
with open(f"{RECIPIENT}/quickscale.yml") as f:
    r = yaml.safe_load(f)

new_modules = set(d["modules"].keys()) - set(r["modules"].keys())
for mod in sorted(new_modules):
    r["modules"][mod] = d["modules"][mod]

with open(f"{RECIPIENT}/quickscale.yml", "w") as f:
    yaml.dump(r, f, default_flow_style=False, sort_keys=False)
```

```bash
# Review quickscale.yml — remove any modules not wanted for this project
cd "$RECIPIENT"
quickscale apply
```

---

### Executor phase 6 — Module React surface adoption (reference only)

For **fresh current-theme recipients** (generated post-SA105): all module React
pages for blog, crm, listings, forms, and social are unconditionally present as
SA105 dormant files from generation. They are present but inactive —
runtime-gated by `window.__QUICKSCALE__.modules` flag checks. Do not copy module
pages from the donor; the recipient already has them.

For **legacy pre-SA105 recipients** (updated in-place): there is **no retroactive
dormant-file guarantee** for any module surface. Blog, crm, listings, forms, and
social pages may all be absent before the continuation runs. Running `quickscale
apply` in a legacy user-owned frontend does **not** guarantee or backfill blog,
crm, or listings surfaces. The shipped post-apply adoption copies only missing
forms/social module-owned surfaces (FormsPage.tsx,
SocialLinkTreePublicPage.tsx, SocialEmbedsPublicPage.tsx, social components,
and usePublicSocialSurface.ts) and preserves existing destinations — it does
**not** backfill blog, crm, or listings.

**If blog, crm, or listings surfaces are missing after the continuation
completes, the maintainer must stop, record the compatibility gap, and
restore/reconcile the missing surfaces manually before continuing.**

The `validateQuickScaleConfig()` gateway (SA107, in `validateQuickScaleSeam.ts`)
enforces fail-hard validation: malformed or missing seam data throws an error
rather than falling back to silent defaults. Dashboard module routes are gated
by `App.tsx` via `window.__QUICKSCALE__.modules` flag checks; public-social
surfaces are dispatched by `renderQuickScaleRoot()` after validation. No manual
route wiring or page-copy steps are needed for the dormant files in fresh
current-theme recipients.

---

### Step 7 — Confirm verification and commit

```bash
cd "$RECIPIENT"

# Confirm the continuation report contains seven passed verification_results
# before committing; do not rerun its mutation or verification phases here.
git status
git add -A
git commit -m "chore: update scaffold from $(basename $DONOR)"
```

---

## File classification reference

What to do with each file in each approach.

| File / directory | Fresh-first (DONOR=existing project) | In-place (DONOR=fresh scaffold) |
|-----------------|--------------------------------------|--------------------------------|
| `Dockerfile` | keep RECIPIENT's (already correct) | copy from donor, fix pkg refs |
| `start.sh` | keep RECIPIENT's, fixing package refs during identity reconciliation | copy from donor, fix package refs |
| `docker-compose.yml` | keep RECIPIENT's | copy from donor, fix pkg/slug refs |
| `.pre-commit-config.yaml` | keep RECIPIENT's | copy from donor |
| `frontend/vite.config.ts`, `tsconfig*.json` | keep RECIPIENT's | copy from donor |
| `frontend/src/hooks/useModules.ts` | keep RECIPIENT's — project-agnostic per SA106 (no baked identity; runtime from `window.__QUICKSCALE__`) | copy from donor (infrastructure target; generic DONOR_PKG/DONOR_SLUG substitutions applied; no projectName-specific patch) |
| `frontend/src/main.tsx` | keep RECIPIENT's (byte-identical only among projects from the same theme version; legacy pre-SA107 or customized recipients must compare/review for boot-validation and public-surface-handoff parity — parity is not proven) | keep RECIPIENT's (byte-identical only among projects from the same theme version; legacy pre-SA107 or customized recipients must compare/review for boot-validation and public-surface-handoff parity — parity is not proven) |
| `pyproject.toml` | keep RECIPIENT's; add any missing path deps from donor | merge: donor non-path dep versions + recipient path deps; preserve recipient pytest settings |
| `frontend/package.json` | keep RECIPIENT's | merge: donor scripts + deps, keep recipient name |
| `quickscale.yml` | keep RECIPIENT's (already has target modules) | edit: add new modules from donor |
| `.quickscale/state.yml` | keep RECIPIENT's authoritative state; reconcile project identity and package-prefixed managed-file keys under the state lock | keep RECIPIENT's authoritative state; `quickscale apply` updates it |
| `<pkg>/settings/modules.py` | auto-generated — keep RECIPIENT's | auto-generated |
| `<pkg>/urls_modules.py` | auto-generated — keep RECIPIENT's | auto-generated |
| `railway.json` | auto-generated — keep RECIPIENT's | auto-generated |
| `modules/` | already embedded in RECIPIENT — keep | embedded by `quickscale apply` |
| `frontend/src/App.tsx` | copy from donor (custom routing); shipped gated routes (React.lazy via SA105) guaranteed only for **fresh current-theme recipients**; legacy/customized recipients must review/reconcile App.tsx | keep RECIPIENT's; shipped gated routes (React.lazy via SA105) guaranteed only for **fresh current-theme recipients**; legacy/customized recipients must review/reconcile App.tsx manually when routing changes are needed |
| `frontend/src/pages/` (custom) | copy pages only in DONOR (Home, About, etc.) | keep RECIPIENT's |
| `frontend/src/pages/` (scaffold) | keep RECIPIENT's (fresher; all module pages already present as dormant files per SA105) | keep RECIPIENT's |
| `frontend/src/components/` (custom) | copy from donor (home/, layout/, shared/, seo/, properties/) | keep RECIPIENT's |
| `frontend/src/components/ui/` | keep RECIPIENT's (fresh shadcn) | keep RECIPIENT's |
| `frontend/src/components/` (new modules) | keep RECIPIENT's (social/, forms/ — present as SA105 dormant files in fresh scaffold) | keep RECIPIENT's (blog/crm/listings not backfilled; forms/social components adopted in post-apply step if missing) |
| `frontend/src/assets/`, `data/`, `types/`, `stores/` | copy from donor | keep RECIPIENT's |
| `<pkg>/urls.py`, `views.py`, `middleware.py`, `sitemaps.py`, `context_processors.py` | copy from donor | keep RECIPIENT's |
| `<pkg>/settings/production.py` | copy from donor | keep RECIPIENT's |
| `<pkg>/settings/base.py`, `local.py` | keep RECIPIENT's | keep RECIPIENT's |
| `media/`, `.env`, `poetry.lock` | never copy; the throwaway recipient's `.env` receives identity-only reconciliation for local verification and remains excluded from repo replacement | never touch |

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

# 2. If initial catch-up used fresh current-theme generation, or if legacy in-place catch-up completed manual reconciliation of missing blog/crm/listings, all dormant surfaces are present (SA105) — no manual copy needed. If legacy in-place catch-up did not reconcile missing blog/crm/listings, do not assume they exist; stop and handle manually first.
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
[ ] Fresh-first throwaway recipient prepared, or for in-place the checkpoint report emitted from a clean migration branch
[ ] Fresh-first report confirms complete field-aware identity reconciliation, including authoritative `.quickscale/state.yml`, derived database/frontend values, and `start.sh`
[ ] Fresh-first report confirms App.tsx, custom pages/components, utilities, Django files, and missing path deps were copied
[ ] In-place checkpoint report reviewed; continuation report confirms infrastructure files including `start.sh` and `validateQuickScaleSeam.ts` were copied with separate slug/package semantics
[ ] In-place continuation report confirms pyproject.toml and frontend/package.json were merged
[ ] In-place continuation report confirms quickscale.yml was updated and `quickscale apply` completed
[ ] In-place only: fresh current-theme recipients already have all module surfaces as dormant files (SA105); legacy pre-SA105 recipients have no retroactive dormant guarantee for any surface — running `quickscale apply` does not guarantee or backfill blog/crm/listings; only missing forms/social surfaces are adopted in post-apply step; missing blog/crm/listings require manual reconciliation before continuing
[ ] In-place only: recipient-owned `App.tsx` reviewed manually when newly added modules need dashboard routing changes (App.tsx gates ordinary module routes; renderQuickScaleRoot() dispatches public-social surfaces); main.tsx requires comparison/review for legacy pre-SA107 or customized recipients (validateQuickScaleConfig() validates seam fail-hard — parity not proven)
[ ] Tool report contains seven passed verification results: `poetry lock`, `poetry install`, `pnpm install`, `pnpm build`, `quickscale manage migrate`, `pytest`, and `pnpm test`
[ ] Local smoke-test completed — existing pages intact and new module pages work
[ ] Effective donor-owned production settings contain the complete SA68 env-pair bridge and both immutable command allowlists before the current maintainer tool is invoked
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
[ ] Blog/crm/listings/forms/social dormant surfaces present if initial catch-up used fresh generation or legacy recipient was manually reconciled; if legacy in-place catch-up skipped manual reconciliation, confirm surfaces exist before proceeding
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
`settings/production.py` to define both immutable `_KNOWN_*` command allowlists
and implement the complete env-pair bridge before either migration mode starts,
regardless of whether `REDIS_URL` is set.

A pre-SA68 production settings file that still uses the former
`"migrate" in sys.argv` branch is therefore incompatible with the current
command. Reconcile that donor-owned file first by adopting the current env-pair
definitions and control flow while preserving its unrelated site configuration;
do not replace it wholesale. Commit and verify that bridge reconciliation before
invoking `make beta-migrate-fresh` or `make beta-migrate-in-place`. Do not use
Redis presence to justify a launcher-first run of the current automation.

### Non-blocking validation findings preserved

- **Orgs module test context:** Orgs module tests require module-local pytest context for direct module runs (not triggered from the root `pytest`). This is a test-tooling affordance, not a gap.
- **Runtime smoke e2e:** The runtime smoke e2e tests remain explicitly marked (`pytest -m e2e`) and opt-in. They are not part of the default `make test` run.

## AI assistant continuation guide

Use this when the maintainer tool is only partially implemented or stops intentionally at a review checkpoint.

1. Read this playbook, the current [v0.89.0 release note](../releases/release-v0.89.0.md), and the historical [v0.81.0 tooling note](../releases/release-v0.81.0.md) before changing the automation behavior.
2. Determine the mode from the provided `DONOR` and `RECIPIENT` values rather than inferring from directory names.
3. Resume from the last completed deterministic step in the tool's report instead of rerunning earlier destructive steps.
4. Fresh-first continuation order: field-aware identity fix (including locked authoritative state reconciliation and `start.sh`) → frontend copies → Django file copies → path dependencies → local verification → manual repo handoff.
5. In-place continuation order after the emitted checkpoint report or explicit continuation opt-in: infrastructure copies (including field-aware `start.sh` reconciliation) → config merges → `quickscale.yml` review → `quickscale apply` → post-apply adoption of missing forms/social module-owned surfaces only (does **not** guarantee or backfill blog/crm/listings; legacy pre-SA105 recipients have no retroactive dormant guarantee for any surface) → local verification → manual review of recipient-owned `App.tsx` when newly added modules need routing changes (App.tsx gates ordinary module routes; renderQuickScaleRoot() dispatches public-social surfaces after validateQuickScaleConfig() validates the seam fail-hard). Legacy pre-SA107 or customized recipients must compare/review main.tsx because parity of boot validation and public-surface handoff is not proven. If blog/crm/listings surfaces are missing after continuation, the maintainer must stop, record the gap, and restore/reconcile them manually before continuing.
6. If a step would require guessing about module adoption, deploy timing, or secrets, stop, record the skipped work in `skipped_steps`, and leave the operator follow-up in `pending_manual_actions`.
7. The minimum handoff payload for partial automation is `mode`, `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions`.

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

### Frontend build fails after fresh-first or in-place file-copy steps

A copied file imports something not yet present in the recipient. Read the build error message,
find the missing import in the donor's `frontend/src/`, and copy only that file.

### `tomli_w` not installed

```bash
pip install tomli-w
```

Or run the pyproject.toml merge manually: copy only the donor's non-path
`[tool.poetry.dependencies]` entries into the recipient, keep the recipient's
`quickscale-module-*` path dependencies, and leave the recipient's
`[tool.pytest.ini_options]` block unchanged.

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
For the in-place workflow, verify Step 2 preserved the donor `FROM` line. For the fresh-first workflow, verify the fresh scaffold still uses `python:3.14-slim-bookworm` before continuing.

### `django-markdownx` import error at startup

The blog module requires `django-markdownx`. For the in-place workflow, confirm Step 3 merged it from the donor's non-path dependencies. For the fresh-first workflow, confirm the fresh scaffold already includes it before rerunning `poetry lock && poetry install`.
