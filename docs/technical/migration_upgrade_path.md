# Website Migration Upgrade Path (Authoritative)

> **Related docs**: [decisions.md](./decisions.md) | [roadmap.md](./roadmap.md) | [beta-site-migration.md](../planning/beta-site-migration.md)

This companion owns the two-stage upgrade path for newer projects: the `website_migration`
maintainer tool plus the maintained recipient prompt. [decisions.md](./decisions.md) remains the
tie-breaker.

## Two-stage path

**Decision:** One upgrade path in two stages.

- ✅ `website_migration` MUST perform the deterministic work: classification, identity
  reconciliation, the file copies, project-owned app carry, dependency merges, the design port,
  and the local verification stack.
- ✅ The tool MUST emit every unresolved gap it recorded into the recipient's
  `MIGRATION_PROMPT.md` in the prompt's remaining-work form: the action slug, its detail, its
  paths, and the governing rule.
- ✅ The prompt-driven port (`MIGRATION_PROMPT.md`, worked with `CUTOVER.md` for the live step)
  MUST close only what the tool reports it could not.
- ✅ The emitted prompt MUST name its format version (`HANDOFF_PROMPT_VERSION`) from the versioned
  renderer in QuickScale, so the recipient does not rely on a copy only it holds.
- ✅ The emitted module list MUST be a divergence triage, not a verdict: classification compares
  donor module content against the recipient's current modules, so the list holds both older
  copies the current content supersedes and real local edits.
- ✅ The [gap ledger](../planning/beta-site-migration.md#gap-ledger) MUST be the prompt's input:
  an iteration's open gaps arrive as remaining-work items, and the ledger records what each stage
  covered so neither stage repeats the other.

## Boundary rule

A gap that recurs across releases MUST move into code — a `tool fix`, a `playbook step`, or an
`upstream to module` change. A one-off MUST stay in the prompt as a `project decision`.

The 2026-10 gap ledger is the worked example: the pre-facade settings rewrite (G-001), the carried
migration operations (G-002), the missing CI/runtime environment inheritance (G-008, G-009), the
carried Django symbols (G-010), and the adopted package-root modules (G-011) each became tool
behavior; the staged wheelhouse export (G-004) became a playbook step; and the pre-port manual-port
surfaces (G-007) stayed with the prompt as a recorded decision.

## Revocation trigger

A second long-lived project or a template security fix MUST revoke the two-stage split. The prompt
stage is written for one port at a time, and a security fix MUST ship in code the generator and the
tool control, not in a prompt a port skips. Supporting further projects meets the "second
long-lived project" trigger.

## Count to watch

The count is declared adoption steps per release: 58 on 2026-10-23 (61 at the 2026-10-29 audit).
The target is zero: `website_migration` and the playbook MUST absorb what the port did by hand, and
SA277 (b) re-counts the count against the cutover evidence.

## Port evidence — what the tool covered, what the port did by hand

From the landed `bap-web-new` run report and the prompt's recorded slices:

| Area | Covered by |
|---|---|
| Preflight, file classification, and identity reconciliation | `website_migration` |
| Frontend page and component copies, selected Django files, symbol merge | `website_migration` |
| Project-owned app carry, registration, URL mount, migration regeneration | `website_migration` |
| Pre-facade `settings/production.py` rewrite onto the runtime facade | `website_migration` |
| Path-dependency sync, frontend dependency merge, and the donor design port | `website_migration` |
| Local verification stack and the handoff prompt | `website_migration` |
| Reconciling the donor's divergent frontend sources and tests (the pre-port surfaces) | the prompt-driven port |
| Triaging the donor's module divergences (older copies accepted, local edits upstreamed or re-expressed) | the prompt-driven port |
| Test parity, live parity, and the committed design baselines | the prompt-driven port |
| The cutover script, its reseed step, and the rehearsal | the prompt-driven port (`CUTOVER.md`) |
| Repinning to the moving `v89` tree and the module re-embed | the prompt-driven port |

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md](../others/arch-audit.md) |
[beta-site-migration.md](../planning/beta-site-migration.md)
