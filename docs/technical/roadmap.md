# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

`v88` is release-accepted (see [CHANGELOG.md](../../CHANGELOG.md)). The next goal is the first
useful property portal (SA153) in a project-owned extension, generalizing capabilities only after
that project proves their value. The portal is built on `bap-web`, the existing beta site, after
the verified migration tools (SA152) move it onto current QuickScale (SA191).

**Release status — v0.88.0 packaged, not published.** The v0.88.0 release commit carries a
release-prepared public note; `v89` has since bumped the repository to `0.89.0`. No core tag,
split-branch republication, seal, or PyPI upload has happened. Outstanding before publication:
release-tier validation on the packaged bytes, the ordered phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. Two scheduled fixes
bear on what gets published: SA186 guards the split-branch force-push that publication runs, and
SA185 declares the `orgs` contract vintage that the 0.88 templates introduced. Landing either in
0.88.0 means repackaging; publishing without them ships the recorded issues. Publication itself
stays a maintainer decision; this planner tracks only that it is owed.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
scope and acceptance; [context](v88_ticket_context.md) explains implementation concepts;
[CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA180 | Derive the gate-parity count oracles from the registry | post-v88 | 1 | — | Deferred |
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 1 | SA180 | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | SA152 | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA182, SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA184 | Make `quickscale deploy railway` re-runs read live state and fail hard | post-v88 | 2 | — | Deferred |
| SA185 | Enforce contract vintage when upgradable code meets an older project | post-v88 | 2 | SA184 | Deferred |
| SA186 | Require a fast-forward before publication force-pushes a split branch | post-v88 | 2 | — | Deferred |
| SA187 | Reject non-ASCII tokens and signatures as authentication failures | post-v88 | 2 | — | Deferred |
| SA182 | Enroll marker-declared tenant models in classification and policy refresh | post-v88 | 3 | — | Deferred |
| SA183 | Refuse to purge an organization with a live Stripe subscription | post-v88 | 3 | — | Deferred |
| SA177 | Verify the predicates of enrolled RLS policies | post-v88 | 3 | SA182 | Deferred |
| SA188 | Settle the privileged-command set behind one declaration | post-v88 | 3 | SA185 | Deferred |
| SA189 | Provision the runtime database role in one place under one name | post-v88 | 3 | SA188 | Deferred |
| SA190 | Derive the purge plan and share organization-removal obligations | post-v88 | 3 | SA182, SA183 | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA180 ──► SA152 ──► SA191 ──► SA153 ──► SA154 (inventory)   critical path: first property portal
Track 2: SA184 ──► SA185 ──► SA186 ──► SA187
Track 3: SA182 ──► SA183 ──► SA177 ──► SA188 ──► SA189 ──► SA190

Cross-track dependencies:  SA182 ──► SA153     SA185 ──► SA188
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA180 → SA152 → SA191 → SA153, with SA182 joining at SA153. The portal is built
on the migrated `bap-web`, so the migration tools are verified first and then used for real. SA182
is small and first on Track 3, so it lands long before SA153 needs it. SA154 is an inventory, not
work. Every other ticket is off the critical path.

**Ordering.**

- **SA182 precedes SA153 and SA177.** Without it the portal's first tenant table fails the generated
  project's `check_tenant_isolation`, or needs module-source edits the extension contract forbids.
  Landing it before SA177 lets predicate verification cover project-owned tables and keeps the two
  out of `tenancy.py` at the same time.
- **SA183 precedes SA190.** Both edit `purge_organization.py`. SA183 is the small money-path refusal;
  SA190 then folds it into the shared obligation list, on top of SA182's derived tenant set.
- **SA184 precedes SA185.** Both edit `deployment_commands.py`, and the deploy-time vintage check
  should read Railway state through the fail-hard path.
- **SA185 precedes SA188, and SA188 precedes SA189.** SA188 changes contract-bearing templates and
  is the first real use of an enforced vintage move. SA188 and SA189 both edit `start.sh.j2` and
  regenerate the SA90 emission fixture; settle the command set before collapsing role provisioning
  around it.
- **SA180 precedes SA152** because SA152 registers a new gate, which then becomes the first use of
  the derived counts instead of another hand edit.
- **SA152 precedes SA191, and SA191 precedes SA153.** `bap-web` is migrated with the maintainer
  tools only after SA152 has proven them on isolated fixtures, and the portal is built on the
  migrated project rather than on a fresh one. SA184 is not an edge: SA191 redeploys through
  `deploy railway` only if SA184 has landed, and otherwise deploys manually.
- **Independent.** SA186 and SA187 have no edges and sit by severity. SA152 shares no files with
  SA188/SA189, but all three touch the privilege/runtime contract of generated `settings/production.py`
  and `start.sh`; whichever lands second re-runs the others' fixtures.

**Rebalance.** Track 1 carries the whole critical path: the migration-tool verification (SA180,
SA152), the `bap-web` migration (SA191), and the portal (SA153), because each feeds the next and
splitting them across tracks would only add merge handoffs. Tracks 2 and 3 split the audit work by
conflict surface. Track 2 takes the CLI deploy/update, publication, and test surfaces, which are
mostly trivial or small. Track 3 takes orgs tenancy, purge, and the privileged/runtime-role
templates, which carry the medium tickets. SA177 sits ahead of SA188 so Track 3 keeps working while
Track 2 delivers SA185. SA186 and SA187 could move to Track 3's tail without a conflict, but would
only lengthen that track.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA180 | yes, after merging `v89` into the stale worktree | yes | yes | **yes** | **yes** |
| 2 | SA184 | yes | yes | yes | **yes** | no |
| 3 | SA182 | yes, after merging `v89` into the stale worktree | yes | yes | **yes** | **yes** (feeds SA153) |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the maintainer
  migration tools and playbook, the `bap-web` migration, the property extension, public templates,
  and the portal's extension documentation.
- Track 2 owns `scripts/publish_module.py`, the CLI deploy and update commands
  (`deployment_commands.py`, `railway_utils.py`, `module_commands.py`, the vintage check), version
  expectations in tests, and the blog/notifications credential comparisons.
- Track 3 owns the isolation-conformance runner, `orgs/tenancy.py` and its checks, the orgs policy
  template/tests, `purge_organization.py` and the account-delete obligations, and the privileged
  command and runtime-role stations (`orgs/apps.py`, `production.py.j2`, `start.sh.j2`,
  `db/init.sql.j2`, `development_commands.py`, the SA90 emission fixture).
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** The shared closeout set is this roadmap, [CHANGELOG.md](../../CHANGELOG.md),
  [ticket context](v88_ticket_context.md), and the owning audit: the arch audit for SA180, SA152,
  SA182, SA185, SA188, SA189, and SA190; the tech audit for SA177, SA183, SA184, SA186, and
  SA187 (SA183 and SA190 also close arch-audit items). SA191 has no owning audit; its evidence goes
  to the changelog and the migration playbook. All are Markdown with no generated consumer.
  Two code-adjacent overlaps cross tracks: SA182 and SA153 both edit the extension and
  organizations documentation (SA182 lands first), and SA189 edits `deployment_commands.py` after
  Track 2's deploy work has merged through its dependency chain. The serialized queue covers them:
  each track resolves the shared set at its own merge, after the previous merge lands, then runs the
  consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

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

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale with the fresh-first migration tool.**

  Use `make beta-migrate-fresh` with `bap-web` as donor and a fresh scaffold generated with the same
  slug as recipient, continuing manually only where the tool emits `pending_manual_actions`.

  **Acceptance:** the migrated project records the current QuickScale version in `quickscale.yml`
  and its lock, and passes its own test suite and local verification stack. The project-owned
  `properties` app, its migrations and catalog seed, forms and contact customizations, content,
  and frontend pages carry over and behave as before; `.git`, `media/`, `.env`, and `poetry.lock`
  are not copied. Every manual step the tool did not automate is recorded in the migration report
  and fed back into the playbook, or into a tool fix when it is deterministic. The migrated project
  replaces the old repository and deploys, with a written rollback to the previous deploy;
  redeploying through `deploy railway` requires SA184, and otherwise the deploy is manual. No
  property-portal features, frontend stack change, or module-source edits.

  **Surfaces:** the `bap-web` repository; the migration playbook and, for deterministic gaps found,
  `quickscale_devtools/.../beta_migration.py` and its tests.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one Django-rendered public surface, using the documented
  project-owned extension pattern for property models, views, URLs, filters, and templates. No public
  JSON API, second React implementation, or generic property behavior in every generated project.

  **Open decision before work starts:** whether the public surface stays Django-rendered as written
  here or becomes React over a JSON API, which `bap-web` already has.

  **Acceptance:** the `bap-web` project migrated by SA191 serves an organization-scoped property
  catalog and detail page with ordered image galleries; bedrooms, bathrooms, area, property type,
  sale/rent, and explicitly labeled currency fields; keyword and attribute filters. Public listing
  and blog pages share a theme and render in Spanish. A listing inquiry creates a CRM record with a
  listing reference. Detail pages have Open Graph output; the site has a sitemap and `robots.txt`.
  Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests,
  and passes the generated project's `check_tenant_isolation` through SA182's enrollment, with no
  edit under vendored module source. Prove the search → detail → inquiry journey and isolation
  between organizations. Correct reusable-module feature claims that the module does not provide.
  No production data cutover; purging an organization that owns property rows is SA190's.

  **Surfaces:** the project-owned property extension and public templates; listings/blog/forms/CRM
  seams only where needed; extension documentation.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: public read API and alternate frontend; generalizing the property extension into
  reusable modules; broader translations; maps/geocoding; saved searches, favorites, and alerts;
  agent/office profiles; syndication; tours/video; paid placement; blog/listing cross-links; and
  PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables (saved searches, favorites, profiles,
  tours) build on SA182's enrollment and SA190's purge derivation, not on module-source edits. Close
  when every item is promoted or dropped with rationale.

- [x] **SA181 — Derive expected versions in tests from the repository version.**

- [ ] **SA184 — Make `quickscale deploy railway` re-runs read live state and fail hard.**

  **Acceptance:** a re-run reuses the service's existing `SECRET_KEY` and generates one only on first
  deploy, mirroring the `RUNTIME_DB_PASSWORD` reuse rule. When Railway variables cannot be read —
  an exception or a `None` result — the command raises `click.ClickException` instead of treating
  state as empty, so it never regenerates the runtime password or overwrites an operator-managed
  `RUNTIME_DATABASE_URL`. `_setup_postgres_step` fails when listing fails or when anything other than
  exactly one database service matches, preferring Railway's service type to a name substring when
  the JSON exposes it. Regressions cover key reuse, the unreadable-state refusal, and zero or several
  Postgres matches. This retires TA74 and TA75.

  **Surfaces:** `deployment_commands.py`, the `railway_utils.py` variable helpers, CLI deploy tests,
  `docs/deployment/railway.md`, and the technical audit.

- [ ] **SA185 — Enforce contract vintage when upgradable code meets an older project.**

  **Acceptance:** `orgs` declares `contract_vintage.minimum: 0.88.0` with manual adoption steps for
  `settings/production.py`, `start.sh`, and the `Dockerfile`, and the CLI declares the same minimum
  for the runtime-role variables `deploy railway` writes. `quickscale update`, `apply`, and
  `deploy railway` run the vintage check that `quickscale status` already computes and refuse when
  the project's recorded contract is behind, unless the operator explicitly acknowledges it; the
  refusal names the module or command, the minimum, and the adoption steps. Regressions prove an
  old-vintage project is refused, and that acknowledged and current projects proceed. Document the
  rule that a change to a contract-bearing emitted file moves the owning vintage. No template
  updater; deriving vintages from the SA90 fixture is out of scope.

  **Surfaces:** the `orgs` manifest, the manifest loader and `status_command.py` vintage check (reuse),
  `module_commands.py` update, `apply_command.py`, `deployment_commands.py`, CLI tests, upgrade
  documentation, and the architecture audit.

- [ ] **SA186 — Require a fast-forward before publication force-pushes a split branch.**

  **Acceptance:** before each push, `--publish-all` (and single-module publication, which relies on
  the same lease) requires the observed remote tip to be an ancestor of the local split. On
  divergence the batch stops before any further push and names the module. A regression with a
  non-ancestor remote tip refuses; a fast-forward republish proceeds. This retires TA77.

  **Surfaces:** `scripts/publish_module.py`, its tests, the publish procedure where it describes the
  lease, and the technical audit.

- [ ] **SA187 — Reject non-ASCII tokens and signatures as authentication failures.**

  **Acceptance:** the blog API token check and the notifications webhook signature check compare
  bytes, or reject non-ASCII input first, so a non-ASCII `Authorization` token or signature header
  gets 401/403 instead of a 500 traceback. Each path has a regression. This retires TA78.

  **Surfaces:** `blog/views.py`, `notifications/services.py`, their tests, and the technical audit.

- [ ] **SA182 — Enroll marker-declared tenant models in classification and policy refresh.**

  **Acceptance:** `is_classified_in_registry()` accepts a model for which `is_tenant_model()` holds,
  as the derived overview already does, while W003/W004 and `check_tenant_isolation` still require
  `organization_id` and FORCE RLS. `refresh_force_rls_policies()` iterates the derived tenant-model
  set instead of `TENANT_TABLE_REGISTRY`. A regression with a non-module tenant model (a project app
  subclassing `AbstractListing`) is classified and refreshed, and the same model without FORCE RLS
  still fails. The literal registry remains only as a shipped-module cross-check; `tenancy.py`, the
  `checks.py` remediation hint, `organizations.md`, and decisions agree on which classifier is
  authoritative, and the extension documentation says how a project declares a tenant table. Purge
  membership is SA190's.

  **Surfaces:** `orgs/tenancy.py`, `orgs/checks.py`, orgs tests, `organizations.md`,
  `module-extension.md`, decisions, and the architecture audit.

- [ ] **SA183 — Refuse to purge an organization with a live Stripe subscription.**

  **Acceptance:** before its atomic block, `purge_organization` raises `CommandError` when the
  organization has a `Subscription` in `Subscription.current_statuses()` with a non-empty
  `stripe_subscription_id`, lists those ids, and tells the operator to cancel first; the dry run
  reports the same refusal. No Stripe call runs inside the purge transaction, and an out-of-band
  acknowledgement flag is out of scope. A variant of `test_purge_organization_with_billing_rows`
  shows an active Stripe-backed subscription refuses and leaves every row and the organization
  intact, while a cancelled one still purges. This retires TA73 and the architecture audit's red
  flag.

  **Surfaces:** `purge_organization.py`, its orgs tests, the purge operator documentation, and both
  audits.

- [ ] **SA177 — Verify the predicates of enrolled RLS policies.**

  **Acceptance:** for each enrolled table — including marker-declared project tables, through
  SA182's derived set — compare both policies' `qual` and `with_check` in `pg_policies` against the
  rendered expected policies, normalized for PostgreSQL's catalog representation. A deliberately
  weakened predicate fails for the intended reason and the exact policy is restored afterward. Then
  retire the tech audit's predicate-conformance tooling gap and structural smell.

  **Surfaces:** isolation-conformance runner, orgs policy template/tests, technical audit.

- [ ] **SA188 — Settle the privileged-command set behind one declaration.**

  **Acceptance:** first record in decisions whether `migrate_billing_to_orgs` is a permanent member
  or is retired; this answers the architecture audit's open question and supersedes the 2026-08-31
  "permanent two" answer. If retired, remove it from the orgs guard, `production.py.j2`,
  `development_commands.py`, and the `start.sh.j2` argv branch, and return the item to the
  watchlist with a dated retirement. If permanent, a privileged command declares itself on its
  command class; the orgs guard and the launcher read that declaration, settings validate only that
  privileged mode was requested explicitly, and every station keeps its own fail-closed refusal.
  Either way, each executable station has a regression naming every member, the SA90 emission
  fixture is regenerated once, and the template change moves the `orgs` vintage through SA185.

  **Surfaces:** `orgs/apps.py`, `migrate_billing_to_orgs.py`, `production.py.j2`, `start.sh.j2`,
  `development_commands.py`, generator/CLI/boot-guard tests, the SA90 fixture, decisions,
  `docs/deployment/railway.md`, and the architecture audit.

- [ ] **SA189 — Provision the runtime database role in one place under one name.**

  **Acceptance:** `db/init.sql.j2`, the `start.sh.j2` provisioning step, the `deploy railway` default
  role, and `OPERATIONS.md.j2` share one role-naming rule and one provisioning statement set,
  including `GRANT CONNECT`. A generated project's local and Railway paths produce the same role name
  and grants, and a regression fails when they diverge. The template change moves the `orgs`
  vintage through SA185. The boot guard and the privileged-command set are unchanged.

  **Surfaces:** `db/init.sql.j2`, `start.sh.j2`, the generator's role-name context,
  `deployment_commands.py`, `OPERATIONS.md.j2`, generator tests, the SA90 fixture, and the
  architecture audit.

- [ ] **SA190 — Derive the purge plan and share organization-removal obligations.**

  **Acceptance:** `purge_organization` takes its membership from SA182's derived tenant-model set and
  its deletion order from installed FK metadata, with explicit overrides, so purging an organization
  that owns project-owned tenant rows succeeds without a `_DELETE_SPECS` edit. The obligations of
  removing an organization — the SA183 billing refusal, owned-row purge, social cache invalidation,
  and tombstone — are one named list that both `purge_organization` and the account-delete view
  consume; the view records which obligations it deliberately skips (retained organization data)
  instead of omitting them. The last-owner model/signal backstop is unchanged. Regressions purge a
  non-module tenant model with a child row cleanly, and a conformance test fails when a purged model
  carries an external provider id with no refuse-or-reconcile obligation. This retires the purge
  half of `org-model-universe-hand-enumerated`, the first step of
  `deletion-invariants-per-boundary-reimplementation`, and the tech audit's teardown tooling gap. No
  durable deletion job or outbox.

  **Surfaces:** `purge_organization.py`, `auth/views.py` account deletion, the billing cancellation
  seam, orgs and auth tests, `organizations.md`, and both audits.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings and their growth triggers. Items they record without scheduling — the watchlists
and watch notes, the generated-project dependency-scan tooling gap, and the later
deletion-coordinator options — stay there until a trigger fires. The standing
no-`teams`/no-third-updater scope, internal-only devtools, presence contracts, and resource
safeguards live in
[decisions](decisions.md) and [validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
