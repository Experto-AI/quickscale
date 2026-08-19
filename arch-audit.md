# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-07-26 · **Current reconciliation:** 2026-08-19 · **Branch:** `v87`

## Current posture

QuickScale is a Python/Poetry Django scaffolding platform with a Click CLI, apply/recovery tooling, and twelve shipped first-party modules; `teams` remains a README-only placeholder. Generated projects use Django 6, PostgreSQL 18, Vite/React, Docker, and Railway. Its public contracts are the CLI, `quickscale.yml` and applied state, module manifests, generated trees, and upgrade semantics.

The current structural posture is stable at the reviewed trust boundaries. Quality-baseline monotonicity and release-gate topology are enforced; their closed findings are archived in [CHANGELOG.md](CHANGELOG.md). Three findings remain open but intentionally outside the `now` horizon. The immediate release path is ordered acceptance (`SA112f`), the apply-path quality repair (`SA140`), and staged publication (`SA96-PUBLISH`); see the [roadmap](docs/technical/roadmap.md).

## Enforcement census

| Invariant | Enforcement | Posture |
|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural and stable |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` checks; privileged command contract | Structural and stable |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated |
| Core/module dependency direction | Import compatibility and reverse-import gates | Gated |
| Module manifest snapshots equal source manifests | Manifest-sync byte comparison | Gated |
| Manifest readers choose source vs bundled inventory consistently | Shared fallback seam plus direct-caller census | Structural, gated, merged |
| Every emitted path has a migration disposition | Generator-derived conformance test over the ownership taxonomy | Membership gated; ownership remains hand-authored (Finding 7) |
| Tenant-model universe is classified | Marker-derived overview cross-checked against the 45-entry registry | Gated |
| Purge order respects FK dependencies | 21-entry manual order and three explicit relation checks | Partial gate (Finding 4) |
| Last-owner deletion is rejected through ORM paths | Canonical predicate, locked model delete, `pre_delete` receiver | Structural; other cleanup remains boundary-owned (Finding 2) |
| Frontend runtime config is complete and typed | `window.__QUICKSCALE__` validation plus frontend proof | Structural and gated |
| Local, hosted, publish, and E2E-trigger gates share one topology | `scripts/gate_registry.json`, parity and generation checks | Structural cause resolved |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus structured waiver ledger | Gated |
| Installed artifacts perform their supported lifecycle | Permanent installed-wheel E2E and generated trigger contract exist; roadmap SA112f owns ordered acceptance | Partial; release-critical acceptance remains |

## Open findings

| Rank | Finding | ID | Horizon | Confidence | Size |
|---:|---:|---|---|---|---|
| 1 | 7 | `generated-file-ownership-unmodeled` | 6–18 months / next updater consumer | High | M |
| 2 | 2 | `deletion-invariants-per-boundary-reimplementation` | deferred to a second deletion boundary | High | S |
| 3 | 4 | `org-model-universe-hand-enumerated` | deferred to tenant-model growth | High | M |

**No finding is at the `now` horizon.** These findings are not v87 release blockers.

### Finding 7 — Generated-file ownership remains a hand-authored updater taxonomy

**Trigger:** Promote when a third generated-project consumer, public updater, emitted-file expansion, or second theme is scheduled.

**Problem:** The generator knows what it emits, but beta migration independently assigns upgrade behavior through a hand-authored taxonomy. The updater carries 138 list/map entries across required donor/recipient, identity, infrastructure, protected, substituted, unmanaged, and module-react categories.

**Evidence and safeguards:**

- `get_generator_emission_mapping()` is authoritative for emitted membership, while `quickscale_devtools/beta_migration.py` owns disposition.
- The conformance test proves every emitted path is classified and fails loudly on omissions; it does not prove the ownership decision is generator-owned or semantically correct.
- SA114 was a recent paid synchronization: a new emitted frontend seam required matching taxonomy edits.
- One supported theme, byte-parity gates, and only two private updater consumers keep the current manual policy defensible.
- Primary evidence lives in `quickscale_core/src/quickscale_core/generator/generator.py`, `quickscale_devtools/src/quickscale_devtools/beta_migration.py`, and `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`.

**Options:**

1. Add typed ownership/disposition metadata to generator emission entries and derive beta-migration collections. This removes the copy while retaining explicit human policy.
2. Emit a versioned ownership manifest for generated projects. This supports vintage negotiation but requires a pre-manifest migration contract.
3. Keep the taxonomy and conformance gate. This is acceptable only while the named growth trigger remains false.

**Recommendation:** Take Option 1 when the trigger fires; add Option 2 only for a public updater that needs vintage negotiation. First characterize the existing 138-entry policy, then derive updater behavior without changing user-visible ownership.

### Finding 2 — Cleanup invariants terminate at the account-delete boundary

**Trigger:** Promote when `teams`, a GDPR erasure command, bulk-admin deletion, or another account/organization deletion boundary is scheduled.

**Problem:** Last-owner safety is structural, but billing cancellation and other cross-domain cleanup are orchestrated only by the account-delete view. A second boundary would need to rediscover and order those effects.

**Evidence and safeguards:**

- `OrganizationMembership.is_last_owner_with_members()` is consumed by locked model deletion and protected by an orgs `pre_delete` receiver.
- Account, HTML member, and JSON member deletion all use that backstop.
- Account deletion alone cancels personal-organization subscriptions; no domain deletion service or billing backstop owns that obligation for a second boundary.
- The current single user-facing deletion flow is covered, and network work in Django signals would be a poor premature abstraction.
- Primary evidence lives in the orgs model/app receiver and the auth/orgs deletion views under `quickscale_modules/`; a future boundary copying the account-view billing cleanup is the promotion signal.

**Options:**

1. Add an explicit account/organization deletion coordinator with idempotent domain contributors.
2. Put local safeguards/outbox records in each domain; safer against bypass, but network effects complicate transactions.
3. Model deletion as a durable lifecycle/job; strongest recovery, excessive until multi-store erasure exists.

**Recommendation:** Take Option 1 when the trigger fires, preserving the existing last-owner model/signal backstop. Design it with Finding 4 at `teams` kickoff so the new domain is integrated once.

### Finding 4 — Organization purge order manually shadows the FK graph

**Trigger:** Promote when `teams` adds a tenant model or any module adds a `PROTECT`/non-deferrable dependency among purge-owned rows.

**Problem:** Tenant-model membership is derived and gated, but `_DELETE_SPECS` manually orders 21 models while tests assert only three CRM relations. Because purge uses `_raw_delete` and composite FKs are `NOT DEFERRABLE`, the list is load-bearing.

**Evidence and safeguards:**

- The 45-entry tenant registry is cross-checked against marker-derived concrete models.
- Purge membership is exact, atomic, and fail-loud; database constraints prevent silent partial deletion.
- The ordering is not exhaustively derived or validated against all installed FK edges.
- Primary evidence lives in `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `management/commands/purge_organization.py`, and the orgs management-command tests.

**Options:**

1. Topologically derive the purge plan from installed model metadata while retaining explicit labels/filter annotations.
2. Let modules publish purge descriptors/dependencies; clearer domain ownership, but still a distributed registry.
3. Keep execution order explicit and add a complete graph validator; lower migration risk, but preserves duplication.

**Recommendation:** Use Option 3 as a characterization gate, then Option 1 when the trigger fires. Preserve deterministic reporting and explicit overrides for semantics that model metadata cannot express.

## Current interactions and load-bearing decisions

- Findings 2 and 4 should be designed together at `teams` kickoff: derive/validate the model dependency graph first, then attach deletion contributors.
- Finding 7 extends the authoritative generator emission mapping rather than introducing a second scanner.
- Tenant isolation remains dual-layer and fail-closed: ambient manager scoping plus restricted-role `FORCE RLS`.
- Frontend project/module truth crosses the validated runtime seam; do not restore generation-time source specialization.
- Source-required manifest operations remain fail-hard; bundled manifests are inventory metadata, not module source.
- Last-owner safety remains a model/signal backstop and must not be weakened by a future coordinator.

## Live watchlist

- **Module universe repeated in environment lists:** promote when a thirteenth shipped module must be added to two or more ungated lists. Not fired; teams is not shipped.
- **SA92 migration-squash discovery tuple:** promote when another migration-bearing module is added or the tuple omits one. Not fired.
- **Frontend runtime module keys:** promote when a new frontend-bearing module requires edits at three ungated stations. Not fired.
- **Privileged-command template/runtime pair:** promote on a third sanctioned command or a mismatch. Not fired.

## Question that changes ranking

What is the first post-0.87 domain/consumer: `teams`, a third generated-project updater, or neither? `teams` promotes Findings 2/4; a third updater promotes Finding 7.

## Reconciliation

- `generated-file-ownership-unmodeled`: open, gated on consumer growth.
- `deletion-invariants-per-boundary-reimplementation`: open but deferred, gated on a second deletion/erasure boundary.
- `org-model-universe-hand-enumerated`: open but deferred, gated on tenant-model growth.

Closed findings, retired watch items, historical option records, and cross-reference migrations are archived in [CHANGELOG.md](CHANGELOG.md) and version control rather than repeated in this live audit.
