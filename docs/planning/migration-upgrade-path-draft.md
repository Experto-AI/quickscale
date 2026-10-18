# Migration upgrade path — draft decision record

> **Draft for SA277 (a2).** This is SA277 (a1)'s handoff note: not policy until it lands in
> [decisions.md](../technical/decisions.md). It is drafted from SA191's landed `bap-web` port
> and rehearsal; (a2) confirms or amends it against the cutover evidence, moves it into
> decisions, and prunes the operator docs of steps either stage covers.

**Decision:** One upgrade path in two stages. `beta_migration` does the deterministic work it
can — classification, identity reconciliation, the file copies, project-owned app carry,
dependency merges, the design port, and the local verification stack — and emits every
unresolved gap it recorded into the recipient's `MIGRATION_PROMPT.md`, in the prompt's own
remaining-work form (the action slug, its detail, its paths, and the governing rule). The
prompt-driven port (`MIGRATION_PROMPT.md`, worked with `CUTOVER.md` for the live step) closes
what the tool reports it could not. The emitted module list is a divergence triage, not a
verdict: classification compares donor module content against the recipient's current modules,
so the list holds both older copies the current content supersedes and real local edits. The
[gap ledger](beta-site-migration.md#gap-ledger) is the prompt's input: an iteration's open gaps
arrive as remaining-work items, and the ledger records what each stage covered so neither stage
repeats the other.

**Boundary rule (draft):** a gap that recurs across releases moves into code — a `tool fix` or
a `playbook step`; a one-off stays in the prompt — a `project decision`. The 2026-10 gap ledger
is the worked example: the pre-facade settings rewrite (G-001), the carried migration
operations (G-002), the missing CI/runtime environment inheritance (G-008, G-009), the carried
Django symbols (G-010), and the adopted package-root modules (G-011) each became tool behavior;
the staged wheelhouse export (G-004) became a playbook step; and the pre-port manual-port
surfaces (G-007) stayed with the prompt as a recorded decision.

**Revocation trigger (draft):** a second long-lived project, or a template security fix, revokes
the two-stage split — the prompt stage is written for one port at a time, and a security fix
must ship in code the generator and the tool control, not in a prompt a port may skip.

**Count to watch:** declared adoption steps per release — 50 on 2026-10-16, counted from the
project contract's declared step list ([arch audit](../others/arch-audit.md)) — trending toward
zero as `beta_migration` and the playbook absorb what the port did by hand.

## Port evidence — what the tool covered, what the port did by hand

From the landed `bap-web-new` run report and the prompt's recorded slices:

| Area | Covered by |
|---|---|
| Preflight, file classification, and identity reconciliation | `beta_migration` |
| Frontend page and component copies, selected Django files, symbol merge | `beta_migration` |
| Project-owned app carry, registration, URL mount, migration regeneration | `beta_migration` |
| Pre-facade `settings/production.py` rewrite onto the runtime facade | `beta_migration` |
| Path-dependency sync, frontend dependency merge, and the donor design port | `beta_migration` |
| Local verification stack and the handoff prompt | `beta_migration` |
| Reconciling the donor's divergent frontend sources and tests (the pre-port surfaces) | the prompt-driven port |
| Triaging the donor's module divergences (older copies accepted, local edits upstreamed or re-expressed) | the prompt-driven port |
| Test parity, live parity, and the committed design baselines | the prompt-driven port |
| The cutover script, its reseed step, and the rehearsal | the prompt-driven port (now `cutover.md`) |
| Repinning to the moving `v89` tree and the module re-embed | the prompt-driven port |

**Related docs:** [roadmap](../technical/roadmap.md) | [arch-audit](../others/arch-audit.md)
| [beta-site migration playbook](beta-site-migration.md)
| [maintained prompt copy](beta-site-migration-prompt.md)
| [maintained cutover copy](beta-site-cutover.md)
