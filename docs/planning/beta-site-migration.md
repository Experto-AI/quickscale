# Beta Site Migration Playbook

A guide for keeping `experto-ai-web` and `bap-web` current with new QuickScale releases.

Trigger prompt for the manual agent-assisted fallback:
> "I have a new quickscale project at `/tmp/xxxx`, incorporate the current web at `$HOME/current-web` — follow `docs/planning/beta-site-migration.md`"

## Planned maintainer automation surface (v0.81.0)

This playbook is being formalized as a beta-site-only maintainer workflow for `experto-ai-web` and `bap-web`.

```bash
make beta-migrate-fresh DONOR=/abs/path/to/existing-beta-site RECIPIENT=/abs/path/to/fresh-scaffold
make beta-migrate-in-place DONOR=/abs/path/to/fresh-scaffold RECIPIENT=/abs/path/to/existing-beta-site
```

Rules for the planned maintainer tool:
- backed by Python scripts under `scripts/`, not a QuickScale module and not a public `quickscale` CLI command
- `DONOR` and `RECIPIENT` are the only required operator inputs and must be provided explicitly on every run
- prefer deterministic Python transforms over bash-heavy pipelines
- if a step cannot be resolved safely, stop and emit a partial report with `completed_steps`, `skipped_steps`, `changed_files`, and `pending_manual_actions` for a maintainer or AI coding assistant to continue
- until the tooling lands, the reference workflows below remain canonical

---

## Two approaches for a major catch-up

| Approach | Working directory | What gets copied | Use when |
|----------|------------------|-----------------|----------|
| **Fresh-first (primary)** | Fresh scaffold at `/tmp/xxxx` | Custom content from existing project → fresh scaffold | You want a clean starting point; infrastructure is correct from the start |
| **In-place (alternative)** | Existing project at `$HOME/current-web` | Infrastructure files from a fresh scaffold → existing project | You want to stay in the existing git repo and not move files |

Both produce the same end result. The fresh-first approach is recommended because the fresh scaffold already has a correct, up-to-date `Dockerfile`, `pyproject.toml`, and frontend build config with no merges required.

After the initial catch-up, use **ongoing maintenance** for all future updates.

## Deterministic automation boundary

- **Fresh-first** is the primary deterministic automation target. It can be automated through local verification, while final repo replacement, push, deploy, secret setup, and smoke approval remain explicit operator steps.
- **In-place** can automate the file transforms and verification steps, but should keep a mandatory review checkpoint before `quickscale apply` when new modules or infrastructure diffs appear.
- **Both paths** must avoid copying `.git`, `media/`, `.env`, or `poetry.lock` between projects. Generate derived artifacts only in the active working tree when the workflow explicitly reaches that step.

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

Set both variables explicitly before running any snippet in this section. The tool or assistant derives everything else from these two paths and does not assume fallback locations.

---

### Step 0 — Derive variables

```python
import tomllib, yaml, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml",     "rb") as f: d_toml = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f: r_toml = tomllib.load(f)

DONOR_PKG     = d_toml["tool"]["poetry"]["packages"][0]["include"]  # e.g. "experto_ai_web"
RECIPIENT_PKG = r_toml["tool"]["poetry"]["packages"][0]["include"]  # e.g. "test80"

with open(f"{DONOR}/quickscale.yml")     as f: d_qs = yaml.safe_load(f)
with open(f"{RECIPIENT}/quickscale.yml") as f: r_qs = yaml.safe_load(f)

DONOR_SLUG     = d_qs["project"]["slug"]   # e.g. "experto-ai-web"
RECIPIENT_SLUG = r_qs["project"]["slug"]   # e.g. "test80"

SAME_SLUG = (DONOR_PKG == RECIPIENT_PKG)   # True if same slug was used → no pkg fixes needed
```

---

### Step 1 — Fix the fresh scaffold's project identity

If the fresh scaffold was generated with a different slug than the existing project, update every
reference to the donor's slug/pkg. If slugs are the same, skip this step.

```bash
if [ "$SAME_SLUG" = "False" ]; then
    # quickscale.yml — update slug and package to match existing project
    python3 -c "
import yaml, os
with open('$RECIPIENT/quickscale.yml') as f: r = yaml.safe_load(f)
r['project']['slug']    = '$DONOR_SLUG'
r['project']['package'] = '$DONOR_PKG'
with open('$RECIPIENT/quickscale.yml', 'w') as f:
    yaml.dump(r, f, default_flow_style=False, sort_keys=False)
"
    # Rename the Django package directory
    mv "$RECIPIENT/$RECIPIENT_PKG" "$RECIPIENT/$DONOR_PKG"

    # Fix slug/pkg references in scaffold files
    for f in Dockerfile docker-compose.yml; do
        sed -i "s|${RECIPIENT_PKG}|${DONOR_PKG}|g; s|${RECIPIENT_SLUG}|${DONOR_SLUG}|g" \
            "$RECIPIENT/$f"
    done

    # Fix pyproject.toml package name
    sed -i "s|include = \"${RECIPIENT_PKG}\"|include = \"${DONOR_PKG}\"|g" \
        "$RECIPIENT/pyproject.toml"
    sed -i "s|${RECIPIENT_PKG}|${DONOR_PKG}|g" "$RECIPIENT/pyproject.toml"

    # Fix useModules.ts projectName
    sed -i "s|projectName: '${RECIPIENT_SLUG}'|projectName: '${DONOR_SLUG}'|g" \
        "$RECIPIENT/frontend/src/hooks/useModules.ts"

    # Update variables for remaining steps
    RECIPIENT_PKG="$DONOR_PKG"
    RECIPIENT_SLUG="$DONOR_SLUG"
fi
```

---

### Step 2 — Transplant App.tsx

The existing project's `App.tsx` is the custom SPA router. Replace the scaffold's default version.

```bash
cp "$DONOR/frontend/src/App.tsx" "$RECIPIENT/frontend/src/App.tsx"
```

---

### Step 3 — Transplant custom pages

Copy only pages that exist in the existing project (DONOR) but NOT in the fresh scaffold (RECIPIENT).
These are the truly custom pages (Home, About, Services, CaseStudies, Properties, etc.).
Pages that already exist in the RECIPIENT (fresh scaffold pages like Dashboard, BlogPage, etc.) are
kept as-is — they are newer and should not be overwritten.

```python
import shutil, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

donor_pages     = set(os.listdir(f"{DONOR}/frontend/src/pages"))
recipient_pages = set(os.listdir(f"{RECIPIENT}/frontend/src/pages"))

custom_only = donor_pages - recipient_pages   # pages only in the existing project

for page in sorted(custom_only):
    src = f"{DONOR}/frontend/src/pages/{page}"
    dst = f"{RECIPIENT}/frontend/src/pages/{page}"
    shutil.copy(src, dst)
    print(f"Copied page: {page}")
```

---

### Step 4 — Transplant custom component directories

Copy all component directories from the existing project EXCEPT `ui/` (keep the fresh scaffold's
shadcn components). Overwrite any same-named dirs in the RECIPIENT — the existing project's
`layout/`, `home/`, `shared/` etc. contain the real custom content.
New module component dirs in RECIPIENT that don't exist in DONOR (`social/`, `forms/`) are preserved.

```python
import shutil, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

donor_dirs     = set(os.listdir(f"{DONOR}/frontend/src/components"))
SKIP = {"ui"}   # always keep recipient's fresh shadcn ui components

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

### Step 5 — Transplant src utilities

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

### Step 6 — Transplant custom Django files

Copy the existing project's hand-written Django files into the RECIPIENT's package directory.
If slugs differ they were already fixed in Step 1, so `DONOR_PKG == RECIPIENT_PKG` at this point.

```python
import shutil, os

DONOR       = os.environ["DONOR"]
RECIPIENT   = os.environ["RECIPIENT"]
DONOR_PKG   = os.environ["DONOR_PKG"]      # already set equal to RECIPIENT_PKG

FILES = [
    "urls.py",                    # custom URL routing (healthcheck, sitemap, SPA catch-all)
    "views.py",                   # custom views (404, robots.txt)
    "middleware.py",              # custom middleware (experto-ai-web only)
    "sitemaps.py",                # sitemap definitions (experto-ai-web only)
    "context_processors.py",      # custom context processors
    "settings/production.py",     # production overrides
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

### Step 7 — Update pyproject.toml module path dependencies

The fresh scaffold's `pyproject.toml` already has the right non-module deps (updated versions,
`django-markdownx`, etc.). The only thing to add is path dependencies for any modules in the
existing project that the fresh scaffold doesn't have (if slugs were the same and the fresh
scaffold was generated with fewer modules).

In the recommended case (same slug, fresh scaffold generated with all desired modules), this step
is a no-op. Run it anyway as a safety check.

```python
import tomllib, tomli_w, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml",     "rb") as f: d = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f: r = tomllib.load(f)

# Find path deps in donor that are missing from recipient
donor_paths = {k: v for k, v in d["tool"]["poetry"]["dependencies"].items()
               if isinstance(v, dict) and "path" in v}
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

### Step 8 — Run migrations and verify

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

### Inputs

```
DONOR     = path to the fresh QuickScale scaffold  (e.g. /tmp/test80)
RECIPIENT = path to the existing beta site         (e.g. ~/Code/experto-ai-web)
```

The fresh scaffold is used only as a source of infrastructure files. The existing project's
custom content (pages, components, Django files) stays in place throughout.

Set both variables explicitly before running any snippet in this section. The scaffold path is a required donor input rather than a fallback location.

---

### Step 0 — Derive variables

```python
import tomllib, yaml, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml",     "rb") as f: d_toml = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f: r_toml = tomllib.load(f)

DONOR_PKG     = d_toml["tool"]["poetry"]["packages"][0]["include"]   # e.g. "test80"
RECIPIENT_PKG = r_toml["tool"]["poetry"]["packages"][0]["include"]   # e.g. "experto_ai_web"

with open(f"{DONOR}/quickscale.yml")     as f: d_qs = yaml.safe_load(f)
with open(f"{RECIPIENT}/quickscale.yml") as f: r_qs = yaml.safe_load(f)

DONOR_SLUG     = d_qs["project"]["slug"]
RECIPIENT_SLUG = r_qs["project"]["slug"]

NEW_MODULES = set(d_qs["modules"].keys()) - set(r_qs["modules"].keys())
```

---

### Step 1 — Create migration branch

```bash
cd "$RECIPIENT"
git status   # must be clean; stash if not
git checkout -b migrate/$(basename "$DONOR")
```

---

### Step 2 — Copy infrastructure files (donor → recipient, fix slug refs)

```bash
cp "$DONOR/Dockerfile" "$RECIPIENT/Dockerfile"
sed -i "s|${DONOR_PKG}|${RECIPIENT_PKG}|g" "$RECIPIENT/Dockerfile"

cp "$DONOR/docker-compose.yml" "$RECIPIENT/docker-compose.yml"
sed -i "s|${DONOR_PKG}|${RECIPIENT_PKG}|g; s|${DONOR_SLUG}|${RECIPIENT_SLUG}|g" \
    "$RECIPIENT/docker-compose.yml"

for f in .pre-commit-config.yaml frontend/vite.config.ts \
          frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json \
          frontend/eslint.config.js frontend/postcss.config.js frontend/prettier.config.js; do
    [ -f "$DONOR/$f" ] && cp "$DONOR/$f" "$RECIPIENT/$f"
done

cp "$DONOR/frontend/src/hooks/useModules.ts" "$RECIPIENT/frontend/src/hooks/useModules.ts"
sed -i "s|projectName: '${DONOR_SLUG}'|projectName: '${RECIPIENT_SLUG}'|g" \
    "$RECIPIENT/frontend/src/hooks/useModules.ts"

# main.tsx — only if adding social module
python3 -c "
import yaml
with open('$DONOR/quickscale.yml')     as f: d = yaml.safe_load(f)
with open('$RECIPIENT/quickscale.yml') as f: r = yaml.safe_load(f)
exit(0 if 'social' in d.get('modules',{}) and 'social' not in r.get('modules',{}) else 1)
" && cp "$DONOR/frontend/src/main.tsx" "$RECIPIENT/frontend/src/main.tsx"
```

---

### Step 3 — Merge pyproject.toml

Keep recipient's module path deps; take donor's dependency versions and pytest config.

```python
import tomllib, tomli_w, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/pyproject.toml",     "rb") as f: d = tomllib.load(f)
with open(f"{RECIPIENT}/pyproject.toml", "rb") as f: r = tomllib.load(f)

DONOR_PKG     = d["tool"]["poetry"]["packages"][0]["include"]
RECIPIENT_PKG = r["tool"]["poetry"]["packages"][0]["include"]

module_paths = {k: v for k, v in r["tool"]["poetry"]["dependencies"].items()
                if isinstance(v, dict) and "path" in v}
non_paths    = {k: v for k, v in d["tool"]["poetry"]["dependencies"].items()
                if not (isinstance(v, dict) and "path" in v)}
r["tool"]["poetry"]["dependencies"] = {**non_paths, **module_paths}

pytest_opts = {**d["tool"]["pytest"]["ini_options"]}
pytest_opts = {k: (v.replace(DONOR_PKG, RECIPIENT_PKG) if isinstance(v, str) else v)
               for k, v in pytest_opts.items()}
r["tool"]["pytest"]["ini_options"] = pytest_opts

with open(f"{RECIPIENT}/pyproject.toml", "wb") as f:
    tomli_w.dump(r, f)
```

---

### Step 4 — Merge frontend/package.json

```python
import json, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/frontend/package.json")     as f: d = json.load(f)
with open(f"{RECIPIENT}/frontend/package.json") as f: r = json.load(f)

merged = {**d, "name": r["name"]}

with open(f"{RECIPIENT}/frontend/package.json", "w") as f:
    json.dump(merged, f, indent=2)
    f.write("\n")
```

---

### Step 5 — Update quickscale.yml and run apply

```python
import yaml, os

DONOR     = os.environ["DONOR"]
RECIPIENT = os.environ["RECIPIENT"]

with open(f"{DONOR}/quickscale.yml")     as f: d = yaml.safe_load(f)
with open(f"{RECIPIENT}/quickscale.yml") as f: r = yaml.safe_load(f)

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

### Step 6 — Copy new React pages (only for newly added modules)

```bash
# Social pages
python3 -c "
import yaml, os
with open('$RECIPIENT/quickscale.yml') as f: r = yaml.safe_load(f)
exit(0 if 'social' in r.get('modules',{}) and
     not os.path.exists('$RECIPIENT/frontend/src/pages/SocialLinkTreePublicPage.tsx')
     else 1)
" && {
    cp "$DONOR/frontend/src/pages/SocialLinkTreePublicPage.tsx" "$RECIPIENT/frontend/src/pages/"
    cp "$DONOR/frontend/src/pages/SocialEmbedsPublicPage.tsx"   "$RECIPIENT/frontend/src/pages/"
    cp -r "$DONOR/frontend/src/components/social/"              "$RECIPIENT/frontend/src/components/"
    [ -f "$DONOR/frontend/src/hooks/usePublicSocialSurface.ts" ] && \
        cp "$DONOR/frontend/src/hooks/usePublicSocialSurface.ts" "$RECIPIENT/frontend/src/hooks/"
}

# FormsPage
python3 -c "
import yaml, os
with open('$RECIPIENT/quickscale.yml') as f: r = yaml.safe_load(f)
exit(0 if 'forms' in r.get('modules',{}) and
     not os.path.exists('$RECIPIENT/frontend/src/pages/FormsPage.tsx')
     else 1)
" && cp "$DONOR/frontend/src/pages/FormsPage.tsx" "$RECIPIENT/frontend/src/pages/"
```

---

### Step 7 — Migrate, test, commit

```bash
cd "$RECIPIENT"
poetry lock && poetry install
cd frontend && pnpm install && pnpm build && pnpm test && cd ..
quickscale manage migrate
pytest
git add -A
git commit -m "chore: update scaffold from $(basename $DONOR)"
```

---

## File classification reference

What to do with each file in each approach.

| File / directory | Fresh-first (DONOR=existing project) | In-place (DONOR=fresh scaffold) |
|-----------------|--------------------------------------|--------------------------------|
| `Dockerfile` | keep RECIPIENT's (already correct) | copy from donor, fix pkg refs |
| `docker-compose.yml` | keep RECIPIENT's | copy from donor, fix pkg/slug refs |
| `.pre-commit-config.yaml` | keep RECIPIENT's | copy from donor |
| `frontend/vite.config.ts`, `tsconfig*.json` | keep RECIPIENT's | copy from donor |
| `frontend/src/hooks/useModules.ts` | keep RECIPIENT's, fix `projectName` | copy from donor, fix `projectName` |
| `frontend/src/main.tsx` | keep RECIPIENT's (already has public surface routing) | copy from donor if adding social |
| `pyproject.toml` | keep RECIPIENT's; add any missing path deps from donor | merge: donor dep versions + recipient path deps |
| `frontend/package.json` | keep RECIPIENT's | merge: donor scripts + deps, keep recipient name |
| `quickscale.yml` | keep RECIPIENT's (already has target modules) | edit: add new modules from donor |
| `<pkg>/settings/modules.py` | auto-generated — keep RECIPIENT's | auto-generated |
| `<pkg>/urls_modules.py` | auto-generated — keep RECIPIENT's | auto-generated |
| `railway.json` | auto-generated — keep RECIPIENT's | auto-generated |
| `modules/` | already embedded in RECIPIENT — keep | embedded by `quickscale apply` |
| `frontend/src/App.tsx` | copy from donor (custom routing) | keep RECIPIENT's |
| `frontend/src/pages/` (custom) | copy pages only in DONOR (Home, About, etc.) | keep RECIPIENT's |
| `frontend/src/pages/` (scaffold) | keep RECIPIENT's (fresher) | keep RECIPIENT's |
| `frontend/src/components/` (custom) | copy from donor (home/, layout/, shared/, seo/, properties/) | keep RECIPIENT's |
| `frontend/src/components/ui/` | keep RECIPIENT's (fresh shadcn) | keep RECIPIENT's |
| `frontend/src/components/` (new modules) | keep RECIPIENT's (social/, forms/) | copy from donor |
| `frontend/src/assets/`, `data/`, `types/`, `stores/` | copy from donor | keep RECIPIENT's |
| `<pkg>/urls.py`, `views.py`, `middleware.py`, `sitemaps.py`, `context_processors.py` | copy from donor | keep RECIPIENT's |
| `<pkg>/settings/production.py` | copy from donor | keep RECIPIENT's |
| `<pkg>/settings/base.py`, `local.py` | keep RECIPIENT's | keep RECIPIENT's |
| `media/`, `.env`, `poetry.lock` | never touch | never touch |

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

# 2. Copy new pages if the module ships a React page (use the earlier in-place Step 6 copy patterns when relevant)
# 3. Add route in App.tsx if it's a dashboard page (not needed for public-surface pages)

pytest && cd frontend && pnpm test && cd ..
git add -A && git commit -m "feat: add <module> module"
```

### 2c — Adopt a new React pattern only

```bash
# Compare pages and hooks between current reference and your project
diff <(ls /tmp/test80/frontend/src/pages/)  <(ls ./frontend/src/pages/)
diff <(ls /tmp/test80/frontend/src/hooks/)  <(ls ./frontend/src/hooks/)

# Copy only files that are new (don't exist in recipient) and are relevant
cp /tmp/test80/frontend/src/pages/<NewPage>.tsx    ./frontend/src/pages/

cd frontend && pnpm install && pnpm build && pnpm test && cd ..
```

---

## Module-specific environment variables

Set in Railway dashboard before deploying. Required only for the listed modules.

### `storage`

```
QUICKSCALE_STORAGE_BACKEND=s3          # or: r2
AWS_STORAGE_BUCKET_NAME=<bucket>
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_S3_REGION_NAME=eu-west-1           # R2: auto
AWS_QUERYSTRING_AUTH=false
QUICKSCALE_STORAGE_PUBLIC_BASE_URL=https://cdn.yourdomain.com
# R2 only:
AWS_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
```

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
[ ] Fresh-first throwaway recipient prepared or in-place migration branch created
[ ] Fresh-first only: recipient identity fixed if slug/package differed
[ ] Fresh-first only: App.tsx, custom pages/components, utilities, Django files, and missing path deps copied
[ ] In-place only: infrastructure files copied and slug references fixed
[ ] In-place only: pyproject.toml and frontend/package.json merged
[ ] In-place only: quickscale.yml updated, reviewed, and `quickscale apply` completed
[ ] In-place only: missing module React pages/hooks copied without overwriting existing pages
[ ] Verification stack completed: `poetry lock`, `poetry install`, `pnpm install`, `pnpm build`, `quickscale manage migrate`, `pytest`, and `pnpm test`
[ ] Local smoke-test completed — existing pages intact and new module pages work
[ ] Result committed or staged in the target repo
[ ] Module env vars set in Railway (storage, notifications if added)
[ ] Merged to main and Railway deployment confirmed
[ ] Migrations visible in Railway logs
[ ] Production smoke-test passed
```

### Ongoing maintenance checklist

```
[ ] Branch created
[ ] quickscale update ran (for module code updates)
[ ] quickscale apply ran (for new module additions)
[ ] quickscale manage migrate ran
[ ] New React pages copied if applicable
[ ] pytest passes; pnpm test passes
[ ] Env vars set in Railway for any new modules
[ ] Merged to main; Railway deployment confirmed
```

## AI assistant continuation guide

Use this when the maintainer tool is only partially implemented or stops intentionally at a review checkpoint.

1. Read this playbook and the v0.81.0 roadmap milestone before changing the automation behavior.
2. Determine the mode from the provided `DONOR` and `RECIPIENT` values rather than inferring from directory names.
3. Resume from the last completed deterministic step in the tool's report instead of rerunning earlier destructive steps.
4. Fresh-first continuation order: identity fix → frontend copies → Django file copies → path dependencies → local verification → manual repo handoff.
5. In-place continuation order: infrastructure copies → config merges → module review checkpoint → `quickscale apply` → missing module pages/hooks → local verification.
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

Or run the pyproject.toml merge manually: copy the `[tool.poetry.dependencies]` section from the
donor into the recipient, then re-add the `quickscale-module-*` path dependencies from the
recipient's original version.

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
