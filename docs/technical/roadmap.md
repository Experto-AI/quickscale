# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

`v88` is release-accepted (see [CHANGELOG.md](../../CHANGELOG.md)). The next goal is the first
useful property portal (SA153) in a project-owned extension, generalizing capabilities only after
that project proves their value.

**Release status — v0.88.0 packaged, not published.** The repository is stamped at `0.88.0` with a
release-prepared public note. No core tag, split-branch republication, seal, or PyPI upload has
happened. Outstanding before publication: release-tier validation on the bumped bytes, the ordered
phases in [publish_procedure.md](publish_procedure.md), and the release PR into `main`. Publication
itself stays a maintainer decision; this planner tracks only that it is owed.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
scope and acceptance; [context](v88_ticket_context.md) explains implementation concepts;
[CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | — | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA180 | Derive the gate-parity count oracles from the registry | post-v88 | 2 | — | Deferred |
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 2 | — | Deferred |
| SA177 | Verify the predicates of enrolled RLS policies | post-v88 | 3 | — | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA153 ──► SA154 (inventory)     critical path: first property portal
Track 2: SA180 ──► SA152                 shared gate files, ordered
Track 3: SA177
```

**Critical path.** SA153 is the whole chain to the next milestone; SA154 is an inventory, not
work. SA180, SA152, and SA177 are off the critical path.

**Ordering.** SA180 precedes SA152 because SA152 registers a new gate, which then becomes the first
use of the derived counts instead of another hand edit. SA152 and SA153 are independent because the
portal uses a fresh generated project.

**Rebalance: no move.** SA153 is one coherent review unit (one extension, one journey) and cannot
be split without sharing files. SA152 and SA180 share `scripts/gate_registry.json` and the parity
oracles. Moving SA177 or SA152 would only trade tracks without shortening the critical path.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA153 | yes | yes | yes | **yes** | **yes** |
| 2 | SA180 | yes, after merging `v88` into the stale worktree | yes | yes | **yes** | no |
| 3 | SA177 | yes, after merging `v88` into the stale worktree | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns the property extension, public templates, and extension documentation.
- Track 2 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, and the
  maintainer migration tools.
- Track 3 owns the isolation-conformance runner and the orgs policy template/tests.
- One delivery candidate at a time per track, one serialized merge queue into `v88`.
- **Conflict surface.** The shared closeout set is this roadmap, [CHANGELOG.md](../../CHANGELOG.md),
  [ticket context](v88_ticket_context.md), and the owning audit (arch audit for SA180/SA152, tech
  audit for SA177). All are Markdown with no generated consumer. The serialized queue covers them:
  each track resolves the shared set at its own merge, after the previous merge lands, then runs the
  consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v88`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v88` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one Django-rendered public surface, using the documented
  project-owned extension pattern for property models, views, URLs, filters, and templates. No public
  JSON API, second React implementation, or generic property behavior in every generated project.

  **Acceptance:** a fresh generated project with listings serves an organization-scoped property
  catalog and detail page with ordered image galleries; bedrooms, bathrooms, area, property type,
  sale/rent, and explicitly labeled currency fields; keyword and attribute filters. Public listing
  and blog pages share a theme and render in Spanish. A listing inquiry creates a CRM record with a
  listing reference. Detail pages have Open Graph output; the site has a sitemap and `robots.txt`.
  Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests.
  Prove the search → detail → inquiry journey and isolation between organizations. Correct
  reusable-module feature claims that the module does not provide. No production data cutover.

  **Surfaces:** the project-owned property extension and public templates; listings/blog/forms/CRM
  seams only where needed; extension documentation.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: public read API and alternate frontend; generalizing the property extension into
  reusable modules; broader translations; maps/geocoding; saved searches, favorites, and alerts;
  agent/office profiles; syndication; tours/video; paid placement; blog/listing cross-links; and
  PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Close when every item is promoted or dropped with rationale.

- [ ] **SA180 — Derive the gate-parity count oracles from the registry.**

  **Acceptance:** compute the eight count-pinned oracles in `scripts/test_gate_parity.py` from the
  registry and workflow sources they describe. Keep the closed-universe check and its failure
  messages. A regression shows that adding a gate updates the derived counts without a hand edit;
  that evidence retires the arch-audit watch item. Renaming `trigger_inputs` is out of scope.

  **Surfaces:** `scripts/check_gate_parity.py`, `scripts/test_gate_parity.py`,
  `scripts/gate_registry.json` if a derivation source is needed, and the architecture audit.

- [ ] **SA152 — Verify maintainer migration modes and their runtime compatibility.**

  **Acceptance:** for each migration mode (fresh-first, in-place), derive which version of
  `settings/production.py`, `start.sh`, and `Dockerfile` reaches the recipient, preserving donor
  precedence. In isolated fixtures on a generated donor/recipient pair, prove a compatible combination
  works and an unsupported privileged-command/runtime combination fails for the intended reason; run
  the fresh-first dry-run and in-place checkpoint-only workflows without touching a real project or
  database. Make a missing template root fail instead of `pytest.skip()`. Register the smoke gate,
  keep gate parity green, and correct the migration playbook's version/location claims.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, CLI migration tests, gate registry and
  parity wiring, Make/CI entrypoints as needed, the migration playbook. No public updater, typed
  ownership framework, or changed file precedence.

- [ ] **SA177 — Verify the predicates of enrolled RLS policies.**

  **Acceptance:** for each enrolled table, compare both policies' `qual` and `with_check` in
  `pg_policies` against the rendered expected policies, normalized for PostgreSQL's catalog
  representation. A deliberately weakened predicate fails for the intended reason and the exact
  policy is restored afterward. Then retire the tech audit's predicate-conformance tooling gap and
  structural smell.

  **Surfaces:** isolation-conformance runner, orgs policy template/tests, technical audit.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings and their growth triggers. The standing no-`teams`/no-third-updater scope,
internal-only devtools, presence contracts, and resource safeguards live in
[decisions](decisions.md) and [validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
