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

That single target runs the migration-topology guard, the non-skippable
generated-project proof, and then `test-integration`, `test-bypassrls`, `typecheck`,
`test-e2e`, and `quality`, aborting at the first failing lane. The command literals
live in the `Makefile` rather than in this document, so there is no second copy to
drift.

The generated-project proof is non-skippable: acceptance is **one pass, zero skips**.

### 1.3 Release artifacts

- [ ] `docs/releases/release-vX.Y.Z.md` exists, follows [the template](release_summary_template.md),
      and is labelled a prepared artifact while the tag does not yet exist. It is the **only** file
      created in `docs/releases/` for this version, and it is the note linked from the GitHub tag
      and the release PR. Keep maintainer-only review detail in the release PR or the roadmap —
      never in a second release document, which only drifts against this one.
- [ ] `CHANGELOG.md` carries a version-ordered `- vX.Y.Z` entry. **The publish workflow greps
      `^- v?X.Y.Z\b` and uses that single line as the GitHub Release body**, so it must read as a
      published release before the tag is pushed (see [Phase 5](#phase-5--publish)).

### 1.4 What CI re-checks at publish time

`publish.yml` re-runs the full gate set on the tagged commit by the
[publish-path full-coverage decision](decisions.md#publish-path-gate-coverage) — publish does not
trust upstream. A gate failing there is a real defect; close it by fixing the cause, never by
declaring an exclusion.

---

## Part 2 — Release procedure

Phases are ordered. Phases 1–2 are local and reversible. Phase 3 writes to the remote but is
re-enterable. Phase 5 is irreversible.

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

For each of the twelve modules, observe the current remote SHA and publish against it:

```bash
make publish-module-status                                  # per-module state and next actions
git ls-remote --heads origin splits/<module>-module         # observe the exact 40-hex SHA
make publish-module MODULE=<module> EXPECTED_REMOTE_SHA=<40-hex>
```

`EXPECTED_REMOTE_SHA` is required for every mutable update and must be freshly observed. An absent
remote branch is not authorization, and `ABSENT` is not a valid input.

`make publish-module-status` observes each remote split branch live and, for every module that is
not up to date, prints a ready-to-paste `make publish-module …` line with the full 40-hex SHA
already filled in — so the `git ls-remote` above is a way to confirm the value by hand, not a step
you must perform to obtain it. The SHA is observed when status runs, not when you paste it: if
anything else pushes in between, the lease fails and you re-observe. That is the interlock working,
not a tooling defect.

**Then verify before sealing.** Phases 4a and 4b below are the verification loop; any failure sends
you back to this phase to fix and republish. Nothing is consumed by iterating.

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
quickscale apply \
  --split-ref <module-a>=splits/<module-a>-module \
  --split-ref <module-b>=splits/<module-b>-module   # one apply, one flag per module
quickscale manage createsuperuser
```

`--split-ref` is repeatable and is consumed by a **single** `apply` — it is not one apply per
module. Until the immutable tags exist, embedding needs `--split-ref`, because the default embed path
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

Any defect found in Phase 4a or 4b returns to [Phase 3](#phase-3--publish-the-split-branches-re-enterable).

### Phase 4c — Seal the split tags

```bash
make seal-modules VERSION=X.Y.Z
```

This creates and pushes the twelve immutable split tags. It takes no expected-SHA input: it samples
each branch tip, rereads it, requires the tag to be absent or already at the intended commit, and
verifies after pushing.

Then verify twelve-of-twelve seals and a clean installed all-module apply with **no override**:

```bash
make seal-status VERSION=X.Y.Z
quickscale apply        # no --split-ref, no other override
```

**Sealing is still correctable.** A tag is permanent at PyPI publication, not at push. Until
Phase 5, fix a sealed mistake by deleting the affected remote and local tags, returning to Phase 3,
and resealing ([decisions.md Rule 4](decisions.md#module-version-lockstep)). The tooling refuses to
move a tag on its own; the deletion is the explicit, deliberate override.

### Phase 5 — Publish

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

### Phase 6 — Close out

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
