# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and release finish line

Ship the v88 hardening release: one green release aggregate over the integrated `v88` tip, then
SA160 and TA67 closeout. After that, deliver the first useful property portal in a project-owned
extension, generalizing capabilities only after that project proves their value.

The retained SA160 work is already integrated in `v88`, task-green, and independently attested
(history in [CHANGELOG.md](../../CHANGELOG.md)). Only release-tier acceptance is missing.
Version/release-note work, tagging, publication, and deployment are separate maintainer decisions
after a green verdict.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
scope and acceptance; [context](v88_ticket_context.md) explains implementation concepts;
[CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA160 | Obtain release acceptance for the integrated v88 tip | v88 | 1 | — | Required |
| SA180 | Derive the gate-parity count oracles from the registry | post-v88 | 2 | — | Deferred |
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 2 | — | Deferred |
| SA177 | Verify the predicates of enrolled RLS policies | post-v88 | 3 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | — | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |

Track numbers map to the existing worktrees: **1 = W1 / wt-track1**, **2 = W2 / wt-track2**,
**3 = W3 / wt-track3**. SA154 is an inventory, not an implementation queue.

```text
Track 1: SA160 (v88, critical path) ──► SA153 ──► SA154 (inventory)
Track 2: SA180 ──► SA152            (post-v88; shared gate files, ordered)
Track 3: SA177                      (post-v88)
v88 finish: SA160 green aggregate ──► SA160/TA67 closeout ──► post-v88 merges open
```

**Critical path.** The v88 finish line is a single-link chain: SA160's release aggregate. Nothing
else feeds it, so no move can shorten it; all post-v88 work is off the critical path.

**Ordering.** SA180 precedes SA152 on Track 2 because SA152 registers a new gate, and doing it after
SA180 makes that addition the first real use of the derived counts instead of another hand edit.
SA152 and SA153 are independent — the portal uses a fresh generated project — unless a real-site
cutover through the beta-migration tools is scoped, which would make SA152 a cutover prerequisite.
SA177 is free to use the isolation runner. SA154 follows the working portal.

**Rebalance review (2026-09-11): no move.** SA152 and SA180 share `scripts/gate_registry.json` and
the parity oracles, so splitting them creates a merge hazard. Moving SA177 or SA153 would only swap
idle tracks, and none of them is on the critical path. SA160's remaining work is validation on the
`v88` ref, not a worktree edit, so Track 1 can prepare SA153 in parallel.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA160 | yes — policy already covers the rerun (see its ticket) | yes — its acceptance needs no other track's work | yes — already integrated; it only records a verdict | **yes** | **yes** |
| 1 (next) | SA153 | yes, in a worktree | yes | no — held behind the SA160 verdict | no | no |
| 2 | SA180 | yes, in a worktree | yes | no — held behind the SA160 verdict | no | no |
| 3 | SA177 | yes, in a worktree | yes | no — held behind the SA160 verdict | no | no |

The post-v88 "can merge = no" is a hard ordering rule, not a missing decision: a post-v88 merge into
`v88` before the verdict would change the release candidate and void the aggregate. Integrate those
tracks after SA160 closes. A maintainer decision to cut a separate post-v88 integration branch would
lift it earlier.

### Ownership and merge coordination

- Track 1 owns SA160 closeout, then SA153 and SA154.
- Track 2 owns gate documentation, `scripts/gate_registry.json` and module declarations, and the
  maintainer migration tools (SA180, then SA152).
- Track 3 owns predicate conformance under SA177, including the isolation runner.
- Product implementation stays in worktrees, with one delivery candidate at a time per track and
  one serialized merge queue into `v88`. Post-v88 merges wait for the SA160 verdict.
- **Conflict surface.** The cross-track shared closeout set is this roadmap,
  [CHANGELOG.md](../../CHANGELOG.md), [ticket context](v88_ticket_context.md) when concepts change,
  and the owning audit. All are Markdown with no generated consumer. The serialized merge queue
  covers them: each track resolves the shared set once, at its own merge, after the previous merge
  has landed, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration)
  for routing, cleanup, candidate binding, and review/merge rules.

### Resuming a track

Measure state; do not read it from this planner. Check the assigned branch, divergence from `v88`,
staged/unstaged changes, untracked files, and any merge in progress, then read the diffs and prior
evidence before deciding anything is blocked. A dirty worktree is a recovery step, not a stop
condition.

Preserve before you reconcile: stage an explicit reviewed file list and make a clearly labeled WIP
checkpoint for work that would otherwise be lost. Never `git add .`, never auto-drop a stash, and
never use destructive reset or checkout to manufacture a clean status. Merge `v88` into the
worktree, resolve conflicts there, run the consistency suite, and continue the task's validation.
Merge only the reviewed and accepted delivery, through the serialized queue.

## v88 work

- [ ] **SA160 — Obtain release acceptance for the integrated v88 tip.**

  All implementation is done and integrated; the product bytes (settled at `926811bc`) are
  task-green and independently attested. Everything after them is status-only documentation, so
  under the [validation policy](validation_policy.md#candidate-review-and-integration) no fresh
  review or separate run authority is needed. That policy supersedes the older one-run/no-retry
  rules for verification inside an authorized delivery.

  **Acceptance:** from a clean `v88` tip, run `QS_E2E_INTEGRATION_REF=v88 make ci-e2e`. Preserve
  `pg18-af10`, clean only run-scoped resources, and record the command, exit, commit, and cleanup in
  the changelog. If it is green, close SA160 and TA67 (tech audit) and move this entry to the
  changelog. If it is red, keep the logs, diagnose, and fix in a worktree. A fix that changes product
  bytes needs a review of that delta before you rerun. Do not redo the accepted cookie, identity,
  HTTPS-proxy, header, or middleware work unless new evidence points to a regression.

  **Out of scope:** version/release-note work, tagging, publication, and deployment, which each need
  their own maintainer decision after a green verdict.

## Post-v88 work

- [ ] **SA180 — Derive the gate-parity count oracles from the registry.**

  The architecture audit's count-oracle watch item has **fired** (`d31c6b41` and `437dd0e0` each
  exceeded the more-than-two-edit threshold). Correcting wording does not discharge it.

  **Acceptance:** compute the count-pinned gate-parity oracles from the registry and workflow
  sources they describe, so adding a gate or station cannot leave a stale literal behind. Keep the
  closed-universe check and the existing failure messages loud. Prove with a regression that adding
  a gate updates the derived count without a hand edit. Retire the watch item only with that
  evidence. Renaming `trigger_inputs` is out of scope.

  **Surfaces:** `scripts/check_gate_parity.py`, `scripts/test_gate_parity.py`,
  `scripts/gate_registry.json` if a derivation source is needed, and the architecture audit.

- [ ] **SA152 — Verify maintainer migration modes and their runtime compatibility.**

  Compare outcomes within each migration mode, not membership in constants from different modes.
  Donor-carried `settings/production.py` and substituted infrastructure may be intentional.

  **Acceptance:** name the launcher/settings contract once and derive each mode's effective file
  sources for `settings/production.py`, `start.sh`, and `Dockerfile`, preserving donor precedence.
  In isolated fixtures, prove a compatible combination passes and an unsupported
  privileged-command/runtime combination fails for the intended reason. In the same smoke suite, run
  fresh-first dry-run and in-place checkpoint-only workflows on a generated donor/recipient pair
  without touching a real project or database, and reconcile the in-place database precondition with
  the fresh-database migration policy. Replace missing-template `pytest.skip()` with a tested explicit
  failure. Register the smoke gate, keep gate parity green, and correct the migration playbook's
  version/location claims. The broader ownership-model finding stays behind its growth triggers.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, CLI ownership/migration tests, gate
  registry and parity wiring, Make/CI entrypoints as needed, and the migration playbook. No public
  updater, typed ownership framework, or changed file precedence.

- [ ] **SA177 — Verify the predicates of enrolled RLS policies.**

  **Acceptance:** for each enrolled table, compare both policies' stored `qual` and `with_check` in
  `pg_policies` against the rendered expected policies, accounting for PostgreSQL's catalog
  representation. A deliberately weakened predicate must fail for the intended reason; restore the
  exact policy afterward. Preserve tenant-write/operator-read semantics and existing boundary checks.
  Then retire the tech audit's predicate-conformance tooling gap and structural smell.

  **Surfaces:** isolation-conformance runner, orgs policy template/tests, and technical audit.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one Django-rendered public surface, using the documented
  project-owned extension pattern for property models, views, URLs, filters, and templates. No public
  JSON API, second React public implementation, or generic property behavior in every generated
  project.

  **Acceptance:** a fresh generated project with listings serves an organization-scoped property
  catalog and detail page with ordered image galleries. It needs bedrooms, bathrooms, area, property
  type, and sale/rent fields, keyword and attribute filters, and explicitly labeled currencies.
  Public listing and blog pages share a usable theme and render in Spanish. A listing inquiry creates
  a CRM record with a listing reference. Add a sitemap, `robots.txt`, and Open Graph output for detail
  pages. Correct reusable-module feature claims to match what the module provides. Every new
  tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests. Prove the
  search → detail → inquiry journey and isolation between organizations. Keep property glue in the
  project extension. A real-site data cutover needs a verified migration path and explicit deployment
  scope; this delivery does not authorize production mutation.

  **Surfaces:** the project-owned property extension and public templates first. Touch the
  listings/blog/forms/CRM seams only where needed, plus extension documentation.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: public read API and an alternate frontend; generalizing the proven property
  extension into reusable modules; broader translations; maps/geocoding; saved searches, favorites,
  and alerts; agent/office profiles; portal syndication; tours/video; paid placement; blog/listing
  cross-links; and PostgreSQL full-text search beyond basic keyword filtering.

  Promote an item only with a concrete consumer, bounded acceptance criteria, and a fresh dependency
  and track assignment. Close the inventory when every item is promoted or dropped with rationale.

## Deferred constraints and references

The live [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md)
own deferred findings and their growth triggers. The standing no-`teams`/third-updater scope,
internal-only devtools decision, settled presence contracts, and resource safeguards remain in
[decisions](decisions.md) and [validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
It checks structure, not release verdicts.
