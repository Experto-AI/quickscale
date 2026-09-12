# Publish Quality Check and Release Procedure (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Publish Procedure**
> **Related docs**: [Decisions](decisions.md#module-version-lockstep) | [Validation policy](validation_policy.md) | [Versioning](versioning.md) | [Railway deployment](../deployment/railway.md) | [Release note template](release_summary_template.md) | [Changelog](../../CHANGELOG.md)

This document is the single source of truth for **how a QuickScale release is quality-checked and
published**. It is version-generic: substitute `X.Y.Z` for the release being published.

**What this document owns:** the pre-publish quality gate, the ordered publish phases, the
re-entrancy rules, and the irreversibility boundary.

**What it does not own, and must not restate:**

| Concern | Owner |
|---|---|
| Why the ordering exists; lockstep, embed, and seal *rules* | [decisions.md §Module Version Lockstep](decisions.md#module-version-lockstep) |
| Validation tiers and what each command covers | [validation_policy.md](validation_policy.md#validation-tiers) |
| `VERSION` single-source semantics and the version tool's scope | [versioning.md](versioning.md) |
| Railway mechanics, runtime role SQL, troubleshooting | [railway.md](../deployment/railway.md) |
| Public release-note shape | [release_summary_template.md](release_summary_template.md) |
| Current release status | [roadmap.md](roadmap.md) and [CHANGELOG.md](../../CHANGELOG.md) |

---

## Part 1 — Publish quality check

Every item must be green on **the exact bytes being published**. A version bump changes bytes, so a
verdict earned before the bump does not carry over.

### 1.1 Version and manifest integrity

```bash
make version-check          # VERSION parity across all packages and module manifests
make check-manifest-sync    # module.yml sources equal their core snapshots
make check-core-compat      # quickscale-core lockstep pins equal the derived specifier
```

The `quickscale-core` lockstep pin is **derived**, not hand-maintained. Any module declaring a
`quickscale-core` requirement in its `module.yml` pins the release being published as the floor and
the next minor as the ceiling — for `0.88.0`, `quickscale-core>=0.88.0,<0.89.0`. `make bump-version`
stamps that into every module's `module.yml` and its core snapshot, and `make check-core-compat`
asserts the exact specifier against `VERSION`, so a stale pin is a red gate rather than something to
catch by eye. The e2e constraint literal derives from `VERSION` for the same reason.

Note that `scripts/sync_module_manifests.py --sync` only copies a module-owned `module.yml` to its
core snapshot. It never derives a pin: syncing a stale pin leaves `make check-manifest-sync` green.
Restamp with `make version-update`, not with `--sync`.

`contract_vintage.minimum` is **not** a lockstep field. It is the adoption boundary for projects
whose generation contract predates a module's vintage; leave it alone unless that module genuinely
gained new manual adoption steps.

### 1.2 Release-tier validation

```bash
QS_E2E_INTEGRATION_REF=<integration-branch> make ci-e2e
```

Pass `QS_E2E_INTEGRATION_REF` explicitly — the default is a previous release branch and the
provenance banner will otherwise compare against the wrong ref. **A partial run never satisfies this
gate**; it announces itself as `PARTIAL CI — NOT a full pass`.

Then the closeout lanes from
[validation_policy.md §Clean-Initial Migration Acceptance](validation_policy.md#clean-initial-migration-acceptance-sa151):

```bash
make release-gate
```

The target owns the lane list and the exact pytest invocations, so this document does not
restate them and there is no second copy to drift. It aborts at the first failing lane.

The generated-project proof is non-skippable: acceptance is **one pass, zero skips**.

### 1.3 Release artifacts

- [ ] `docs/releases/release-vX.Y.Z.md` exists, follows [the template](release_summary_template.md),
      and is labelled a prepared artifact while the tag does not yet exist. It is the **only** file
      created in `docs/releases/` for this version, and it is the note linked from the GitHub tag
      and the release PR. Keep maintainer-only review detail in the release PR or the roadmap —
      never in a second release document, which only drifts against this one.
- [ ] `CHANGELOG.md` carries a version-ordered `- vX.Y.Z` entry. **The publish workflow greps
      `^- v?X.Y.Z\b` and uses that single line as the GitHub Release body**, so it must read as a
      published release before the tag is pushed (see [Phase 6](#phase-6--publish)).

### 1.4 What CI re-checks at publish time

`publish.yml` re-runs the full gate set on the tagged commit by the
[publish-path full-coverage decision](decisions.md#publish-path-gate-coverage) — publish does not
trust upstream. A gate failing there is a real defect; close it by fixing the cause, never by
declaring an exclusion.

---

## Part 2 — Release procedure

Phases are ordered. Phases 1–2 are local and reversible. Phase 3 writes to the remote but is
re-enterable. Phase 5 writes immutable remote tags, correctable only by deleting them deliberately.
Phase 6 is irreversible.

**Automation boundary.** Phases 1–4 are executable by a coding assistant: every step is a `make`
target with a red/green verdict, split branches are mutable, and no tag leaves the machine. Phases
5–7 are operator-only — sealing, publication, and close-out each require a judgement that is
expensive or impossible to unwind. An assistant running this procedure stops after Phase 4b and
reports.

### Phase 1 — Stamp the version

```bash
make bump-version X.Y.Z
```

This writes `VERSION` and propagates it to every package, module manifest, core snapshot, and
`quickscale-core` lockstep pin ([§1.1](#11-version-and-manifest-integrity)). Review
`contract_vintage.minimum` if a module genuinely gained manual adoption steps, then commit the
release state with the conventional subject:

```bash
git commit -m "vX.Y.Z: QuickScale X.Y.Z"
```

Run [Part 1](#part-1--publish-quality-check) now. Do not proceed on a red gate.

### Phase 2 — Create the core tag locally

```bash
git tag X.Y.Z          # local only — DO NOT push
```

Tags are bare `X.Y.Z`. **Never run `git push --tags`**: it can push this tag and trigger
publication before the modules are ready. Every push in this procedure names its ref explicitly.

### Phase 3 — Publish the split branches (re-enterable)

Split branches are **mutable working artifacts**. This phase is designed to be repeated as many
times as verification requires — that is the point, not a failure path. Before the first mutating
call, configure repository-local credentials and identity (publication disables system/global Git
config and fails once when any value is absent):

```bash
git config --local credential.helper '<credential-helper>'
git config --local user.name  '<name>'
git config --local user.email '<email>'
```

Keep credentials in the helper or an SSH agent — never in a remote URL or command argument.

Publish each module that is not already up to date, observing its current remote SHA and publishing against
it. On a first pass through this phase that is all twelve; on a re-entry from
[Phase 4a/4b](#re-entry-loop-for-phase-4a4b-defects) it is usually a subset, and status tells you which:

```bash
make publish-module-status                                  # per-module state, and a ready-to-paste line per module
make publish-module MODULE=<module> EXPECTED_REMOTE_SHA=<40-hex>   # paste from status
git ls-remote --heads origin splits/<module>-module         # optional: confirm the SHA by hand
```

`<module>` is the bare directory slug under `quickscale_modules/` — `[a-zA-Z0-9][a-zA-Z0-9_-]*`, expanded
internally to `quickscale_modules/<module>` and `splits/<module>-module`. The twelve authoritative values are
`analytics`, `auth`, `backups`, `billing`, `blog`, `crm`, `forms`, `listings`, `notifications`, `orgs`,
`social`, `storage`. The set comes from the authoritative shipped-module inventory, not from a directory
listing, so an unapproved name fails closed before any push.

`EXPECTED_REMOTE_SHA` is required for every mutable update and must be freshly observed. An absent
remote branch is not authorization, and `ABSENT` is not a valid input.

`make publish-module-status` observes each remote split branch live and, for every module that is
not up to date, prints a ready-to-paste `make publish-module …` line with the full 40-hex SHA
already filled in — so the `git ls-remote` above is a way to confirm the value by hand, not a step
you must perform to obtain it. The SHA is observed when status runs, not when you paste it: if
anything else pushes in between, the lease fails and you re-observe. That is the interlock working,
not a tooling defect. A module whose remote branch is absent gets no paste line, because `ABSENT` is not a
valid `EXPECTED_REMOTE_SHA`.

**There is no bulk publish, by design.** The batch path is disabled because it used a bare `--force`, which
violates the force-with-lease contract that `EXPECTED_REMOTE_SHA` exists to enforce. Publish one module at a
time, each against its own freshly observed SHA; re-running `make publish-module-status` between publishes
reprints the remaining lines. Note the asymmetry with [Phase 5](#phase-5--seal-the-split-tags): sealing
*is* a single bulk command, because a seal takes no lease input and fails closed on its own.

**Then verify before sealing.** Phases 4a and 4b below are the verification loop; a failure there means fixing
the cause, re-running the quality gate, and republishing whatever status then reports as outdated, per the
[re-entry loop](#re-entry-loop-for-phase-4a4b-defects). Nothing is consumed by iterating.

### Phase 4a — Verify by generated project

A locally installed build resolves its own unpublished wheels, so install from the repository first:

```bash
make install            # builds the wheels and stages <venv>/quickscale_wheels
quickscale --version    # expect X.Y.Z
```

Without that staged wheelhouse every generated project pins a `quickscale-core` version PyPI does
not have yet and `quickscale apply` fails at `poetry lock`. `QUICKSCALE_LOCAL_WHEELHOUSE` overrides
the location with an absolute directory.

```bash
quickscale plan myapp        # interactive: theme, modules, Docker options
cd myapp
quickscale apply --split-refs-from-branches
quickscale manage createsuperuser
```

`--split-refs-from-branches` embeds every module from its own `splits/<module>-module` branch. It
derives the same mapping you would otherwise type as a dozen repeated `--split-ref MODULE=REF`
arguments, and covers the embed set exactly by construction, so it can neither miss a module nor
name one that is not being embedded. Use repeated `--split-ref` only when some module needs a ref
that is *not* its own split branch.

Until the immutable tags exist, embedding needs one of those two flags, because the default embed path
resolves `splits/<module>-module/X.Y.Z` and fails closed when that tag is absent
([decisions.md Rule 5](decisions.md#module-version-lockstep)). Overrides must cover **exactly** the
modules being added, they resolve refs on `origin` rather than your working tree, and a local-only
integration branch is therefore not a usable value — which is why Phase 3 comes first.

Services start during `apply`. The site serves on **http://localhost:8000**. Walk the public
surface: `/`, `/blog`, `/listings`, `/orgs`, `/crm`, `/forms`, `/profile`, `/settings`, `/social`,
`/social/embeds`, `/admin/`, `/healthcheck/`. There is no demo-data seeder, so add a post and a
listing through `/admin/` to exercise the public pages. Keep the generated `quickscale.yml` if you
want the same site shape next release.

### Phase 4b — Verify by deployment

Deploy the same generated project and exercise it as a real site:

```bash
quickscale deploy railway
```

This does **not** create the restricted database role, and without it the RLS boot guard raises
`ImproperlyConfigured` at startup because Railway's default role carries `BYPASSRLS`. Follow
[railway.md §Runtime Role Setup](../deployment/railway.md#runtime-role-setup) for the role and
grants, then:

```bash
railway variables --set RUNTIME_DATABASE_URL=postgresql://quickscale_runtime:<pw>@<host>:<port>/<db> --service myapp
railway up --service myapp --detach
```

Create a superuser with the `DJANGO_SUPERUSER_*` Railway variables or
`railway run --service myapp python manage.py createsuperuser`, then confirm the deployed site
loads and the same routes behave. First deploy takes 5–10 minutes.

#### Re-entry loop for Phase 4a/4b defects

Any defect found in Phase 4a or 4b is fixed before sealing and is **never carried past Phase 5**. Fix the
cause where it lives, then replay forward. This loop is written to be executed literally, by a person or by a
coding assistant.

**Loop until Phase 4a and 4b both pass with zero defects:**

1. Run [Phase 4a](#phase-4a--verify-by-generated-project). If it passes, run
   [Phase 4b](#phase-4b--verify-by-deployment). If both pass with no defect, **exit the loop** and go to
   [Phase 5](#phase-5--seal-the-split-tags). Otherwise take the first defect and route it: if its cause is
   a tracked file in this repository, go to step 2; if it is Phase 4b environment state, go to step 4.

2. **Repository defect** — the cause is a tracked file, whether under `quickscale_modules/<module>/` or in
   `quickscale_core/`, `quickscale_cli/`, or `quickscale/`. This also covers a failing `make test`, a bad
   `quickscale apply`, and wrong wheel contents. Fix and commit. Because publication requires a tag at `HEAD`
   matching `VERSION`, keep the same `X.Y.Z` and recreate the local tag after the commit:

   ```bash
   git tag -d X.Y.Z && git tag X.Y.Z    # local only — still never pushed
   ```

   Re-run [Part 1](#part-1--publish-quality-check) in full: a verdict earned before the fix does not carry
   over to the new bytes. Then go to step 3.

3. **Republish exactly what changed.** Run `make publish-module-status` and republish every module it reports
   as `outdated` or `unpublished`, per [Phase 3](#phase-3--publish-the-split-branches-re-enterable). Status is
   the arbiter here — do not decide by hand which modules were affected.

   A split branch carries only its own `quickscale_modules/<module>/` subtree, so a fix confined to core, the
   CLI, or the generator leaves all twelve branches byte-identical and status reports every module up to date.
   That is the expected result, not a missed step: there is nothing to republish, and you return to step 1
   with the rebuilt install from Phase 4a.

4. **Deployment-environment defect** (Phase 4b only) — the cause is outside the repository: a missing runtime
   role, a wrong Railway variable, a bad `RUNTIME_DATABASE_URL`. Fix the environment, re-deploy, and go to
   step 1. No commit, no tag, and no republish are involved.

Nothing is consumed by iterating: split branches are mutable, no tag is pushed, and the version is not spent
until [Phase 6](#phase-6--publish). If the same defect survives two passes, stop and escalate rather than
looping again — a repeating failure usually means the cause was located in the wrong layer at step 2.

This loop runs **before** any tag is sealed. The superficially similar loop for a mistake discovered *after*
sealing is narrower and is described in [Phase 5](#phase-5--seal-the-split-tags) and the
[re-entrancy summary](#re-entrancy-summary); it additionally requires deleting the affected split tags.

### Phase 5 — Seal the split tags

```bash
make seal-modules VERSION=X.Y.Z
```

This creates and pushes the twelve immutable split tags. It takes no expected-SHA input: it samples
each branch tip, rereads it, requires the tag to be absent or already at the intended commit, and
verifies after pushing.

Then verify twelve-of-twelve seals and a clean installed all-module apply with **no override**:

```bash
make seal-status VERSION=X.Y.Z
quickscale apply        # no --split-ref, no --split-refs-from-branches, no other override
```

**Sealing is still correctable.** A tag is permanent at PyPI publication, not at push. Until
Phase 6, fix a sealed mistake by deleting the affected remote and local tags, returning to Phase 3,
and resealing ([decisions.md Rule 4](decisions.md#module-version-lockstep)). The tooling refuses to
move a tag on its own; the deletion is the explicit, deliberate override.

### Phase 6 — Publish

Last chance to reword the `- vX.Y.Z` CHANGELOG line and drop the "prepared" labelling from the
release note — the workflow reads that line for the GitHub Release body at publish time.

```bash
git push origin X.Y.Z
```

**This is the irreversible step.** The tag push triggers `publish.yml`, which verifies the tag
against `VERSION`, re-runs the full gate set, builds with path dependencies rewritten to `^X.Y.Z`,
publishes to TestPyPI then PyPI via Trusted Publishing, verifies every pinned distribution is
actually published, and creates the GitHub Release with the built artifacts attached.

Do **not** also run `make publish-prod` / `scripts/publish.sh prod`. That is a separate manual
upload path for out-of-band situations; running both double-publishes the same version. Pick the tag
push.

After this point the version is spent: a published release can be yanked, never recalled, and a
defect costs a new version.

### Phase 7 — Close out

- [ ] Open the release PR from the integration branch into `main`.
- [ ] Confirm PyPI has all three distributions and the GitHub Release links the public note.
- [ ] Update the `CHANGELOG.md` entry to published wording if anything still reads as prepared.
- [ ] The sealed split tags and the published release now correspond exactly. **Leave them alone** —
      they are the released identity and are never re-pointed.

---

## Re-entrancy summary

| Artifact | Mutable until | How to correct |
|---|---|---|
| Local release commit and tag | always (pre-push) | amend; `git tag -d X.Y.Z` |
| `splits/<module>-module` branches | always | republish with a fresh `EXPECTED_REMOTE_SHA` |
| `splits/<module>-module/X.Y.Z` tags | PyPI publication | delete remote + local tag, republish branch, reseal |
| PyPI distributions and the GitHub Release | never | ship a new version |

Split-tag permanence rests on client-side fail-closed checks and ordinary transport permissions, not
a server-side policy; a force-privileged maintainer can still move a tag. That residual is accepted
and recorded in [decisions.md](decisions.md#module-version-lockstep).

## Ordering rationale

Publishing core before the split branches carry matching manifests ships a `quickscale apply` that
fails for every user selecting any module, because an embedded manifest whose version differs from
the running core is a hard error. `publish.yml` does not enforce this ordering — it only keeps
namespaced split tags from triggering publication — so the ordering is the operator's obligation.
