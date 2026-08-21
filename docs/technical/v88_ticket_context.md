# v88 Ticket Context — Concepts and Implementation Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **v88 Ticket Context**
> **Related docs**: [Roadmap](roadmap.md) (authority for scope, tracks, merge order) | [Decisions](decisions.md) | [Validation Policy](validation_policy.md)

## What this document is

The [roadmap](roadmap.md) says *what* each v88 ticket must achieve and *when* it may run. This companion says *why the problem exists*, *what mental model to hold*, and *where the code actually lives*. It is explanatory, not authoritative: if this document and the roadmap disagree, the roadmap wins.

Read the roadmap ticket first, then the section here.

---

## The one idea behind all nine tickets

Every v88 ticket is an instance of the same structural principle:

> **Every fact should have exactly one home, and every consumer should read it from that home. When a consumer cannot read it, the system should stop, not guess.**

That principle splits into two failure modes, and each ticket fixes one or both:

| Failure mode | What it looks like | Tickets |
|---|---|---|
| **Duplicated authority** — the same fact is written down in two or more places, so they drift | devtools version pinned by hand; Python/Postgres versions retyped in tests; the SA117 required-path set restated in four places; manifest defaults restated in imperative code | SA137, SA134, SA124, SA118 |
| **Silent fallback** — a component cannot find the authoritative answer, so it substitutes a plausible one and continues | wheelhouse set but no wheel matches → returns the manifest spec instead | SA150 |
| **Unowned lifecycle** — a resource is created but nobody is responsible for its identity or destruction | E2E images accumulate; the integration gate assumes a PostgreSQL server someone else started; migration history accretes | SA142, SA135, SA151 |
| **Unenforced policy** — a rule exists only in a human's head | no dependency-vulnerability or security static-analysis gate | SA123 |

If you hold one sentence in your head for the whole release, hold that table. The track grouping in the roadmap follows it directly: **Track 1 is duplicated authority + silent fallback in the version/dependency domain**, **Track 2 is duplicated authority + unenforced policy in the tooling domain**, **Track 3 is unowned lifecycle in the service domain**.

---

# Track 1 — Pins and dependency-spec authority

## SA137 — Add `quickscale_devtools` to version propagation

### The mental model

QuickScale ships several Python packages out of one repository: `quickscale`, `quickscale_core`, `quickscale_cli`, `quickscale_devtools`, and twelve `quickscale_modules/*`. The repository holds **one** version number in the root `VERSION` file, and `scripts/version_tool.sh` is the machine that pushes that number into every place a version is written.

Think of `VERSION` as the single clock, and `version_tool.sh` as the mechanism that moves every hand on every dial. `check` asks "do all the dials agree with the clock?"; `update` sets them.

### The concrete defect

Look at the top of `scripts/version_tool.sh`:

```bash
PYPROJECTS=("$ROOT/quickscale_core/pyproject.toml" "$ROOT/quickscale_cli/pyproject.toml" "$ROOT/quickscale/pyproject.toml")
PACKAGES=("$ROOT/quickscale_core/src/quickscale_core" "$ROOT/quickscale_cli/src/quickscale_cli")
```

`quickscale_devtools` is in neither list. The modules *are* handled well — `_load_module_inventory()` shells out to the authoritative discovery shim (`quickscale_core/src/quickscale_core/contracts/module_discovery.py --list-modules`) and derives the twelve module paths, so adding a module needs no edit here. But the four top-level packages are a **hardcoded array**, and devtools was never added to it.

The drift is already real and observable today:

```
VERSION                                 → 0.87.0
quickscale_devtools/pyproject.toml:34   → version = "0.86.0"
```

Devtools is a release behind, and `make version-check` passes anyway, because it never looks.

### Why it matters (and why it is only Tier 1, not urgent)

Devtools is deliberately **maintainer-only**. Its own `pyproject.toml` header states it is intentionally absent from `PACKAGES` in `scripts/publish.sh` and `DEFAULT_PACKAGES` in `scripts/prepare_publish.py`. So a stale version does not ship to a user.

Hold this distinction clearly, because it is the most likely way to get this ticket wrong:

- **Version *parity*** — devtools should carry the repository version. **This is what SA137 fixes.**
- **Version *publication*** — devtools should be uploaded to PyPI. **This is explicitly NOT SA137.** Adding devtools to the publish package list would break the documented maintainer contract and require `PATH_DEPENDENCY_REWRITES` changes.

If a reviewer sees devtools appear in a publish list, the ticket has overreached.

### Implementation shape

The weak fix is to append devtools to the two arrays. The acceptance criterion "the propagation set is derived, not a second hand-maintained list" rejects that: it recreates the same class of bug for the *next* package. Prefer discovering top-level packages the way modules are already discovered — a directory scan for `quickscale*/pyproject.toml` at the repository root, or a single declared inventory that both `version_tool.sh` and the publish scripts read, with publication remaining a separate flag on each entry.

Note that `scripts/sa117_scope.json` **already lists** `quickscale_devtools/pyproject.toml` and `quickscale_devtools/src/quickscale_devtools/__init__.py` as `SA117 version pin surface` entries. The allowlist expected devtools to be in the lockstep set; the tool never caught up. That is your strongest evidence that this is a genuine omission and not a deliberate exclusion.

Also check whether devtools has a `__version__` in `src/quickscale_devtools/__init__.py` — a grep found none, so decide deliberately whether `update` should write one (matching the module pattern) or whether the `[project] version` alone is the pin surface. Whichever you choose, the scope file's phase-4 entry should match reality afterwards.

### Files

`scripts/version_tool.sh`, `quickscale_devtools/pyproject.toml`, `scripts/test_version_tool.py`, possibly `quickscale_devtools/src/quickscale_devtools/__init__.py`. Shared surface: `VERSION`, `Makefile`.

### Verification

`make version-check` (must now fail before the fix and pass after the devtools bump); `scripts/version_tool.sh update` followed by a clean `check`; new contract tests in `scripts/test_version_tool.py`. Note that `test_version_tool.py` copies the real script into a synthetic repository (`shutil.copy2` at line ~450) — your new discovery logic must work inside that hermetic fixture, so avoid depending on anything outside the copied tree.

---

## SA134 — Derive generated-project version assertions from authoritative pins

### The mental model

A generated QuickScale project pins runtimes: a Python version, a Django constraint, a PostgreSQL image tag, a Node image. Those pins have exactly one home:

`quickscale_core/src/quickscale_core/generator/runtime_pins.py`

```python
PYTHON_VERSION: str = "3.14"
PYTHON_CONSTRAINT: str = f">={PYTHON_VERSION},<3.15"
PYTHON_DOCKER_TAG: str = f"{PYTHON_VERSION}-slim-bookworm"
DJANGO_CONSTRAINT: str = ">=6.0.7,<6.1.0"
POSTGRES_VERSION: str = "18"
POSTGRES_DOCKER_TAG: str = f"{POSTGRES_VERSION}-alpine"
```

The module's own docstring states the intent: *"All templates that reference a pin use the same value from this module, so a single change here propagates to every emitted file."* Templates honour that — `docker-compose.yml.j2` line 3 emits `postgres:{{ postgres_docker_tag }}`.

**The tests do not.** They retype the literal.

### The concrete defect

Files carrying hardcoded `18-alpine`, `node:24`, or `python:3.14` include:

- `quickscale_core/tests/test_generator/test_templates.py`
- `quickscale_core/tests/generator/test_themes.py`
- `quickscale_cli/tests/test_beta_migration.py`
- `quickscale_cli/tests/utils/test_stale_compose_volumes.py`
- `quickscale_cli/tests/utils/test_railway_utils.py`
- `quickscale_core/tests/docker-compose.test.yml`

So `runtime_pins.py` is a single source of truth for *production* and a **second, shadow source of truth for tests**. Bumping PostgreSQL to 19 changes one production line and then breaks a scatter of tests that assert the old value — and the failure message says "expected 18-alpine, got 19-alpine", which reads like a regression rather than "you forgot to update the mirror".

### The subtlety that makes this Tier 2 rather than trivial

A test that reads `POSTGRES_DOCKER_TAG` and asserts the template emits `POSTGRES_DOCKER_TAG` is **tautological** — it will pass no matter what the value is, including nonsense. You are trading a brittle test for a vacuous one if you are careless.

The resolution is to be precise about what each assertion is *for*:

- **"The pin reaches the emitted file"** — derive from `runtime_pins`. This is a wiring assertion; tautology is fine because the point is that the plumbing connects, not what flows through it.
- **"We are not on a retired version"** — keep the literal. This is the *negative control* the acceptance criteria protect. A test asserting `"3.12" not in emitted_dockerfile` stays a literal deliberately, because its whole job is to name a specific bad value.

The acceptance wording — *"retired-version negative controls remain and still fail when a retired version is reintroduced"* — exists exactly to stop a blanket find-and-replace from deleting them.

### The proof obligation

*"bumping a pin requires no test edit, demonstrated by a temporary bump that leaves the suite green"*. Literally do this: change `POSTGRES_VERSION` to `"19"`, run the suite, confirm green, revert. Record it as evidence. If anything fails, a literal survived.

Note `quickscale_core/tests/docker-compose.test.yml` is a static YAML file, not Python — it cannot import `runtime_pins`. Decide whether it is in scope (it pins the *test harness* Postgres, arguably a different concern from the *generated project* Postgres) and say which, rather than leaving it ambiguous. This overlaps SA135, which owns the test harness's database; coordinating the answer with the Track 3 ticket is reasonable, but SA134 merges first, so state the decision and let SA135 honour it.

### Depends on SA137 because

Both tickets are about "the version fact has one home". SA137 establishes the derived-inventory pattern for repository package versions; SA134 applies the same discipline to runtime pins in tests. Sequencing them avoids two people inventing two different conventions for "read the authoritative value" in the same release.

---

## SA150 — Document and fail-hard the `QUICKSCALE_LOCAL_WHEELHOUSE` seam

### The mental model

When QuickScale generates a project, that project needs to depend on `quickscale-core`. Normally the generated `pyproject.toml` says something like `quickscale-core = "^0.87.0"` — resolved from PyPI.

But during development and acceptance testing, the version you want does not exist on PyPI yet. So there is an escape hatch: a **wheelhouse**, a directory of locally built `.whl` files. When one is in play, the generated project should depend on an exact local wheel *file* instead of a PyPI version range.

Two ways a wheelhouse is found (`_resolve_wheelhouse_dir()`, `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py:153`):

1. `QUICKSCALE_LOCAL_WHEELHOUSE` env var — an explicit, deliberate override used by installed-wheel acceptance runs.
2. A wheelhouse staged beside the running CLI install (`sys.prefix/<wheelhouse dirname>`) — implicit, for locally installed builds.

### The concrete defect

`_resolve_local_wheel_dependency()` at line ~175:

```python
wheelhouse = _resolve_wheelhouse_dir()
if wheelhouse is None:
    return None                      # (A) no wheelhouse at all — correct

normalized_name = dependency_name.replace("-", "_").lower()
candidates = sorted(wheelhouse.glob(f"{normalized_name}-*.whl"))
if not candidates:
    return None                      # (B) wheelhouse exists, no matching wheel
if len(candidates) != 1:
    raise DependencySyncError(...)   # (C) ambiguous — correctly fails hard
```

Returning `None` means "no local wheel applies, use the manifest version spec". That is right for **(A)** and wrong for **(B)**.

The two cases are semantically opposite:

- **(A)** You never asked for a wheelhouse. Falling back to PyPI is the correct, intended behaviour.
- **(B)** You explicitly set `QUICKSCALE_LOCAL_WHEELHOUSE` — you *stated* you want local wheels — and the wheel isn't there. Something is broken: a build step didn't run, a name normalization mismatched, the wrong directory was exported. Falling back to `^0.87.0` from PyPI silently produces a project that installs a **different artifact than the one under test**.

Note the asymmetry the code already contains: case **(C)**, two matching wheels, raises. Ambiguity fails hard; absence does not. That inconsistency is the tell.

The failure is quiet and delayed: the acceptance run proceeds, installs a published wheel, and reports success on the wrong artifact — or fails much later at install time with an unrelated-looking error.

### Why this is the second half of the ticket

`_resolve_wheelhouse_dir()` **already** fails hard on a malformed env var:

```python
if not wheelhouse.is_absolute() or not wheelhouse.is_dir():
    raise DependencySyncError(
        f"{_LOCAL_WHEELHOUSE_ENV} must name an absolute wheelhouse directory"
    )
```

So the seam has real, enforced contracts — absolute path, must exist, unambiguous wheels — that appear **nowhere in `docs/technical/`**. The only descriptions are code comments and the E2E test `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`. Someone hitting the error has to read the CLI source to learn the rules. That is the documentation half.

### Implementation shape

Distinguish (A) from (B). Give `_resolve_local_wheel_dependency()` enough information to know *why* there is no wheelhouse — either return a small result type from `_resolve_wheelhouse_dir()` carrying its provenance (explicit-env vs staged-beside-install vs none), or check the env var directly at the raise site. Raise `DependencySyncError` naming the env var, the directory searched, the glob pattern tried, and the wheels actually present — the last of these is what turns a five-minute debugging session into a five-second one.

The staged-beside-install wheelhouse (case 2) is a judgement call: it is implicit, not requested, so an unmatched wheel there is arguably closer to (A). State your choice explicitly in the doc rather than leaving it to be rediscovered.

### Guard rails

- *"a regression test asserts the raise (not a log)"* — a `caplog` assertion does not satisfy this. The call must raise.
- *"the unset-wheelhouse path is unchanged"* — the overwhelmingly common path is no wheelhouse at all. It must keep resolving from the manifest exactly as today. A regression here breaks ordinary project generation for every user.

### Audit bookkeeping

`docs/others/tech-audit.md` currently reports **zero open findings**. The wheelhouse seam is listed under **"Live watch items"**, not as a finding. So the closeout retires a watch item; it does not close a numbered finding, and the severity table stays at zero. (The roadmap's acceptance line has been corrected to match.) While you are in that file, note its header still reads `Branch: v87` — a stale-doc drift worth a one-line fix.

---

# Track 2 — Gates and declared wiring

## SA124 — Unify SA117 scope-tool path authority

### The mental model

SA117 was a large, high-risk refactor around embedded-manifest and core version lockstep. To keep it controllable it was given a **scope guard**: an explicit allowlist of every file any SA117 phase may touch, in `scripts/sa117_scope.json` (~120 entries, each with a `path`, a `phase`, and `notes`). `scripts/check_sa117_scope.py` enforces it in several modes:

- `worktree` — do the changed files fall inside the allowlist?
- `emit` — print the allowlist, optionally filtered by phase
- `lock` — do candidate paths match the allowlist *exactly*?
- `lock-diff` — fail-closed proof that `poetry.lock` did not drift, normalising only the twelve approved module version leaves

Mental model: the allowlist is a **capability boundary**. The tool's job is to make it impossible to change a file nobody agreed to change.

### The concrete defect

A guard whose own contract is restated in several places can drift, and drift in a guard is worse than drift anywhere else — it fails *open*. The "required-path set" (which inputs each mode requires, and which paths it covers) is currently expressed independently in at least four places:

1. **The CLI** — `argparse` in `check_sa117_scope.py` (~line 826): `worktree.add_argument("--paths", nargs="*", default=None)` with a *runtime* check `raise ValueError("--paths is required for worktree mode")` at line 159. Note `--paths` is declared optional to argparse and required by hand later — that gap is itself a small instance of the problem.
2. **The Make target** — `Makefile:916-938` re-implements the same requirement in shell:
   ```make
   sa117-check:
   	@if [ -z "$(PATHS)" ]; then \
   		echo "Error: PATHS is required (space-separated list of changed files)."; \
   ```
   and again for `sa117-lock`, and again with different variables for `sa117-lock-diff` (`SA117_BASELINE_REF`, `SA117_EXPECTED_VERSION`).
3. **`--help` / the Make help text** — `Makefile:234-237` describes the requirements in prose: `"make sa117-lock-diff - Fail-closed poetry.lock drift proof (SA117_BASELINE_REF required)"`.
4. **`scripts/sa117_scope.json`** — the path data itself.

Four statements of one contract. Add a fifth consumer, or change a requirement in one place, and the others silently disagree.

Contrast this with how the same file handles the *module* inventory: `_authoritative_module_names()` (line ~48) shells out to the discovery shim and raises `LockDiffError` if it cannot. That is the pattern this ticket generalises — the file already knows how to do it right for one kind of fact.

### Implementation shape

Define the required-input/required-path contract once — most naturally as data in or beside `sa117_scope.json`, or as a declarative table in `check_sa117_scope.py` that argparse is built from. Then:

- argparse builds its `required=` flags and help strings from it, so `--help` cannot drift.
- The Make target stops re-checking emptiness in shell and lets the tool report the error, or reads the same declaration.
- A test enumerates the consumers and fails if one bypasses the source.

The last bullet is the durable part. *"a test fails if any consumer is added without going through that source"* means the enforcement must be structural, not a comment saying "keep these in sync".

### The advisory

`SA117E1-REV-004` is carried by this ticket. **Be aware before starting: that identifier appears nowhere in the repository except the roadmap line itself** — not in `CHANGELOG.md`, not in `docs/`, not in the scope JSON. Its original text is not recoverable from the tree. Your first action should be locating it (check the v87 review history in version control, or `docs/planning/sa117e-4-corrected-source-plan.md`). If it cannot be recovered, the acceptance criterion's *"or explicitly re-carried with rationale"* branch applies — record that the advisory text is lost and either close it as unrecoverable or restate what you believe it covered. Do not silently drop it.

### Why SA123 depends on this

Both tickets edit `scripts/gate_registry.json` and the `Makefile` gate surface. Doing SA124 first means SA123 registers its new gates against a tidied, single-authority path contract rather than against four drifting copies. Serialising them on one track keeps the registry off the cross-track conflict surface entirely.

---

## SA123 — Add dependency-vulnerability and security static-analysis gates

### The mental model

QuickScale's CI discipline is centralised in `scripts/gate_registry.json` — a declared list of every gating checkpoint, with each gate naming the **contexts** it must run in:

```json
"contexts": {
    "local-serial":  "scripts/check_ci_locally.sh serial mode",
    "local-parallel":"scripts/check_ci_locally.sh parallel mode",
    "hosted":        ".github/workflows/ci.yml hosted CI",
    "publish":       ".github/workflows/publish.yml release workflow",
    "e2e-trigger":   ".github/workflows/e2e.yml ordered path allowlist"
}
```

Each gate entry carries `id`, `description`, `required_contexts`, `bindings` (`make_target`, `ci_job`, `local_ci_stage`), `depends_on`, and `trigger_inputs`. `scripts/check_gate_parity.py` then proves that what the registry declares actually exists in every context — a gate cannot be green locally and absent in hosted CI.

**This is the key insight for the ticket: the registry is the gate's real home. A scanner wired only into `ci.yml` is not a QuickScale gate; it is a workflow step that parity checking will reject.**

### The concrete gap

`docs/others/tech-audit.md` names it precisely under **Tooling gaps**:

> **Dependency vulnerabilities:** no blocking `pip-audit`/Safety-equivalent scanner with a reviewed allowlist. Roadmap SA123 owns this for v88.
>
> **Security static analysis:** no focused Bandit/Semgrep-equivalent rules for subprocess shell use, unsafe deserialization, TLS disabling, Django raw/marked-safe sinks, and committed credentials. SA123 owns this for v88.

That second entry is effectively your rule list. Five named categories — treat them as the scope boundary. "Focused" is doing real work in that sentence: turning on Bandit's full default rule set across a repository this size produces a wall of findings, most of them noise in test code, and the predictable outcome is a blanket suppression that makes the gate decorative.

### Design tensions to resolve deliberately

**Blocking vs advisory.** A dependency-vulnerability scanner queries a database that changes without your code changing. A new CVE published overnight turns a green build red with no commit. That is *correct* — you want to know — but it means the gate can block an unrelated release. Decide and document how a fresh CVE is triaged under time pressure, because the reviewed-suppression mechanism is what stands between you and someone disabling the gate at 2am.

**Suppressions are the deliverable, not an afterthought.** *"every suppression carries a written rationale and an owner"*. A suppression file with entries but no rationale is worse than no gate — it looks like coverage. Model the format on the existing quality-waiver structure (`scripts/quality_waivers.json`) so the repository has one shape for "accepted exception".

**Registration is the acceptance criterion.** Both gates need `scripts/gate_registry.json` entries with correct `required_contexts` and `bindings`, and `scripts/check_gate_parity.py` must pass. Also consider `trigger_inputs`: a dependency scanner's trigger is `poetry.lock` and every `pyproject.toml`, not source files.

### The negative-control requirement

*"the gates fail on a deliberately introduced known-vulnerable pin and on a deliberately introduced flagged pattern, both reverted before merge"*. This is non-negotiable evidence. A scanner that runs, exits 0, and has never been shown to exit nonzero is unproven — misconfigured path filters are the single most common way security scanners silently scan nothing. Capture the failing output in the ticket evidence and revert both probes before merge.

### Files

`scripts/gate_registry.json`, `Makefile`, `.github/workflows/ci.yml`, `scripts/check_ci_locally.sh`, a new suppression/allowlist file, `pyproject.toml` (tool config + dev dependency). `scripts/sync_ci_gate_jobs.py` may need to know about the new jobs. Watch the `make quality` ceiling — the acceptance says leave it no worse than found.

---

## SA118 — Project every declared manifest default into wiring

### The mental model

Each module carries a `module.yml` manifest that **declares** its configuration surface. From `quickscale_modules/storage/module.yml`:

```yaml
config:
  mutable:
    backend:
      type: string
      default: "local"
      django_setting: QUICKSCALE_STORAGE_BACKEND
      validation:
        choices: ["local", "s3", "r2"]
    media_url:
      type: string
      default: "/media/"
      django_setting: MEDIA_URL
  immutable:
    private_media_enabled:
      type: boolean
      default: false
```

Every entry states four things: a type, a default, the Django setting it maps to, and (sometimes) validation. `mutable` options must have a `django_setting` — `quickscale_core/src/quickscale_core/manifest/loader.py:242` enforces it. `ModuleManifest.get_django_settings_mapping()` (`manifest/schema.py:225`) already exposes the name→setting map.

So the declaration is rich and validated. The question SA118 asks is: **does the generated project's wiring actually reflect every declared default, or do some defaults exist only inside imperative Python that re-states them?**

You have already seen a concrete example of the second pattern in SA150's file:

```python
backend = str((module_options or {}).get("backend", "local")).strip().lower()
```

That `"local"` is `storage.backend`'s manifest default, retyped in `module_dependency_sync.py`. Change the manifest and this code keeps the old default. Same class of bug as SA137 and SA134, one layer up.

### The scope boundary — this is the important part

There is a much larger, tempting project here: converting all imperative module wiring to a declarative manifest-driven pipeline. **SA118 explicitly is not that project.** The acceptance says: *"the imperative-to-declarative migration is not attempted — out-of-scope seams are ticketed, not converted."*

The line to hold:

- **In scope:** a default is *declared* in a manifest, and generated wiring does not carry it (or carries a stale copy). Fix the projection.
- **Out of scope:** a behaviour is imperative and has no manifest declaration at all. Do not invent a declaration for it. File a ticket.

The distinction is "is there already a declared fact being ignored?" — not "could this be declarative in principle?"

### Emission parity — expect this to be the bulk of the work

Changing what the generator emits collides with `quickscale_core/tests/fixtures/sa90_emission_manifests.json`. Read its `_provenance` block: it holds *exact path/hash/mode manifests* for three generator variants, deliberately built independently of the production emission mapping so it is a real check and not a mirror.

Its `baseline_evidence` entries show the established convention — each past rebaseline records ticket id, date, what changed, and which specific hashes moved:

> `"sa106": "Regenerated 2026-07-20 — three identity-bearing frontend source templates converted from .j2 to static verbatim-copy files (SA106). ... Deltas: useModules.ts.j2→static, ... 3 fixture hashes updated: useModules.ts, Dashboard.tsx, Sidebar.tsx."`

*"rebaseline emission parity with per-file rationale"* means adding an entry in exactly that register. A bulk regeneration with the note "updated hashes" destroys the fixture's value — the whole point is that a human certified each delta was intended.

### Dependencies

**SA123** — same track, sequencing only. **SA150** — real and cross-track: SA118 touches manifest version-spec handling, and it must sit on top of SA150's fail-hard seam rather than the current silent fallback. This is the single inter-track edge in the release; if the merge order slips, SA118 will build on behaviour that is about to change underneath it.

---

# Track 3 — Service-backed lifecycle

Track 3 holds the **exclusive PostgreSQL/Docker slot** for the release. Only one of these legs may be active at a time across all worktrees, and Track 3 takes priority while a leg is running. All three tickets are about the same question: *who owns the lifecycle of a thing we create?*

## SA151 — Recreate module migrations as clean initial schemas

### The mental model

Django migrations exist to move an **existing** database from schema A to schema B without losing data. That value proposition rests on one assumption: somebody out there is running schema A and needs to get to schema B.

QuickScale is pre-1.0 and explicitly not backward compatible across versions. The documented upgrade path is a **fresh database**. So the assumption does not hold — and migration history becomes pure cost: files to maintain, an ordering graph to keep consistent, and a slower apply.

### The current state

```
analytics:      0 migration files      ← no models, or models with no migration?
auth:           1
backups:        5      ← 0001_initial + 0002…0005
billing:        1
blog:           1
crm:            1
forms:          1
listings:       1
notifications:  1
orgs:           1
social:         1
storage:        0      ← same question as analytics
teams:          0      ← placeholder, not a shipped module
```

`backups` has accreted four incremental migrations (`remote_storage_context`, `restore_scope_and_versions`, `snapshot_substrate`, `restore_execution`) — visible feature history that will never be replayed by anyone, because nobody upgrades a QuickScale database in place. The other modules' `0001_initial` files are described as stale, meaning they no longer match current models even though they are numbered as initial.

`backups/0001_initial.py` is stamped `# Generated by Django 6.0.3 on 2026-03-26` — five months of model evolution sit between that file and today.

### Two things to determine before deleting anything

1. **`analytics`, `storage`, and `teams` have zero migrations.** `teams` is a known placeholder (`PLACEHOLDER_MODULE_NAMES` in `module_discovery.py` excludes it, and `AUTHORITATIVE_MODULE_COUNT = 12`). But `analytics` and `storage` are shipped modules — do they genuinely have no models, or are they missing migrations they should have? If it's the latter, that is a live defect this ticket should surface, and the acceptance phrase *"exactly one `0001_initial` per module with models"* is written to accommodate a legitimate zero.
2. **RLS and the `organization_id` policy.** Regenerating from models is only correct if the models carry everything the current schema has. If any row-level-security policy, index, or constraint lives in a `RunSQL` or `RunPython` step inside `backups` `0002`–`0005` rather than in the models, regeneration **silently drops it** and `makemigrations --check` will still report clean, because it only compares model state. Read all four before deleting them. This is the single highest-risk step in the ticket and the reason it holds the PostgreSQL slot.

### Verification is the real deliverable

- Exactly one `0001_initial` per module with models, nothing else.
- A generated project applies every module migration from an **empty** database in one pass.
- `makemigrations --check --dry-run` reports no pending changes for every module — this is what proves the regenerated files actually match the models.
- `make test-integration` passes.

Add a schema-level comparison if any `RunSQL` was found: dump the schema before and after and diff it. `--check` compares Django's model state, not the database, so it cannot detect a dropped raw-SQL policy.

### Policy record

The no-migration-history policy goes in `docs/technical/decisions.md`. Without it, the next contributor will "helpfully" add `0002_*` and reintroduce the problem. The decision should state the rule *and* the reason (pre-1.0, fresh-database upgrade path), so it can be revisited deliberately at 1.0 when the assumption changes.

---

## SA142 — Reuse and clean E2E Docker images

### The mental model

Every Docker E2E run creates several kinds of object, and they have genuinely different natural lifetimes:

| Object | Should be | Why |
|---|---|---|
| **Image** | *stable and shared* | An expensive build artifact; identical inputs → identical image. Rebuilding it per run is waste. |
| **Container** | *per-run and disposable* | Carries run state; sharing one across parallel lanes causes interference. |
| **Port** | *per-run* | Two lanes on one port collide. |
| **Volume** | *per-run* | Carries database state that must not leak between runs. |

`scripts/test_e2e.sh` gets three of these four right, and rigorously so. Look at lines 483-500:

```bash
lane_container_prefix="$(sanitize_scope "${lane_prefix_base}-${BASHPID}")"
lane_compose_project="$(sanitize_scope "${lane_compose_base}-${BASHPID}")"
export QS_E2E_CONTAINER_PREFIX="$lane_container_prefix"
export COMPOSE_PROJECT_NAME="$lane_compose_project"
```

Per-lane, PID-scoped identity, with `cleanup_scoped_containers()` reclaiming by both the compose-project label and the name prefix, signal traps on TERM/INT/HUP, and a pre-cleanup pass before the run. This is careful code.

### The concrete defect

The image is the one that isn't handled — and the cause is a single missing line in `quickscale_core/src/quickscale_core/generator/templates/docker-compose.yml.j2`:

```yaml
  backend:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        INSTALL_DEV: "true"
    container_name: {{ project_name }}_backend
```

There is a `build:` stanza but **no `image:` key**. When Compose builds a service with no explicit image name, it derives one from the project name: `<compose_project>-backend`.

And `COMPOSE_PROJECT_NAME` is exported as `${lane_compose_base}-${BASHPID}` — deliberately different every run.

So image identity inherits container identity. Consequences:

1. **No reuse.** Every run builds from scratch under a new name, even with byte-identical inputs. That is the "measurably faster second run" the acceptance asks for.
2. **No reclamation.** Cleanup is `docker compose down -v --remove-orphans` plus container removal by label and name. `down` removes containers, networks, and volumes — **not images**. Nothing in the script ever runs `docker image rm` or `docker image prune`. Every run permanently leaks one image.

Confirm the leak before starting: `docker images | grep backend | wc -l` on this machine, given the E2E history, is your baseline evidence.

### Implementation shape

Give the backend service an explicit `image:` whose tag derives from **build inputs**, not from run identity — the Dockerfile, the Python constraint, the lockfile, the installed module set. Content-addressing (a hash of those inputs) gives correct reuse *and* correct invalidation: change an input, get a new tag automatically; change nothing, hit the cache.

Then add image reclamation to the cleanup path for the variable images that remain, filtered by a QuickScale-owned label so you never remove an unrelated user image. **A blanket `docker image prune -a` is unacceptable** — E2E runs on developer machines.

`--no-cleanup` must still preserve everything needed for diagnosis. Its current output tells the user exactly how to clean up by hand (lines 513-516); extend that guidance to images rather than leaving a new class of leftover undocumented.

### Watch out

This edits a **generated-project template**, so it changes emitted output — the SA90 emission-parity fixture will need the same rebaseline-with-rationale treatment described under SA118. Two tickets touching that fixture in one release, on different tracks; the sync-before-merge-back procedure must preserve both entries.

### Depends on SA151 because

Sequencing on the exclusive service slot, not a code dependency. SA151 should hold the PostgreSQL slot first because its migration regeneration is the riskier, more schedule-sensitive leg.

---

## SA135 — Give test suites an owned PostgreSQL lifecycle

### The mental model

Compare the two database-backed gates as they exist today:

**The E2E gate owns its database.** `scripts/test_e2e.sh:535`: *"pytest-docker will automatically start PostgreSQL"*, backed by `quickscale_core/tests/docker-compose.test.yml`:

```yaml
services:
  postgres:
    image: postgres:18-alpine
    ports:
      - "5432"   # Dynamic port — Docker assigns an available host port
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
```

Started on demand, health-checked, dynamically ported, torn down after.

**The integration gate borrows one.** `scripts/test_integration.sh`, header:

```
# Requires PostgreSQL 18 running on localhost:5432.
#
# Prerequisites:
#   - PostgreSQL 18 running on localhost:5432
#   - All test databases pre-created (see ci.yml create-test-databases step)
#   - A LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER role ... with
#     ownership + schema grants on all module test databases
```

Three preconditions that **somebody else** must have satisfied, out of band. On hosted CI a workflow step does it. On a developer machine, a human did it once, months ago, and may not remember how.

SA135 is: make the integration gate own its server the way the E2E gate already does. The pattern is proven and in-tree — this is largely propagation, not invention.

### Why the fix is delicate

The role contract is not incidental. `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — specifically `NOBYPASSRLS` — is what makes row-level-security tests **meaningful**. A superuser bypasses RLS entirely, so isolation tests running as one would pass without proving anything. `scripts/provision_test_roles.sh` and `scripts/test_isolation_conformance.sh` exist to enforce this.

A hasty containerised swap that connects as the default `postgres` superuser would leave every integration test green and every multi-tenant isolation guarantee unverified. That is the worst possible outcome for this repository, given the locked child-table RLS policy. **Preserving the role contract is the acceptance criterion that matters most.**

### The negative control

*"the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping"*.

The tempting shape for provisioning code is:

```python
if not postgres_available():
    pytest.skip("PostgreSQL not available")
```

That converts an infrastructure failure into a green build with silently zero integration coverage — the same silent-fallback family as SA150, one layer up. If provisioning fails, the gate must fail. There is an existing asserted-unavailability control; it must survive the rewrite.

### Proof

*"`make test-integration` passes on a machine with no PostgreSQL running"*. Test it honestly — stop any host PostgreSQL, confirm nothing is listening on 5432, run the gate. If it passes because it quietly found a server you forgot about, you have proven nothing.

### Documentation

`docs/technical/validation_policy.md` currently encodes the out-of-band assumption:

> Integration | `make test-integration` | ... | PostgreSQL 18 per-module test DB | `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER`

and the Testing Standards section describes the precondition in prose. Both need updating — this ticket changes a documented contract, which is why `validation_policy.md` is on its conflict surface.

### Depends on SA142 because

SA135 will provision a containerised PostgreSQL, so it should adopt whatever image-identity convention SA142 establishes rather than seeding a second, competing one. This is a genuine ordering dependency, not just slot scheduling.

---

## Reading order

If you are coming to this cold, read in this order — each builds the model for the next:

1. **SA137** — the smallest, clearest instance of duplicated authority; the whole release's pattern in one file.
2. **SA150** — the clearest instance of silent fallback; four lines of code, precisely diagnosable.
3. **SA134** — duplicated authority plus the tautology trap, which is where judgement starts mattering.
4. **SA142** — lifecycle ownership, with a single missing YAML key as the root cause.
5. **SA151, SA135** — the two service-lifecycle tickets, both carrying real correctness risk (dropped RLS policies; bypassed RLS roles).
6. **SA124, SA123, SA118** — the tooling and wiring tickets, which need the most context about existing conventions (scope allowlist, gate registry, emission-parity fixture).
