# v88 Ticket Context — Concepts and Implementation Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **v88 Ticket Context**
> **Related docs**: [Roadmap](roadmap.md) (authority for ticket metadata) | [Decisions](decisions.md) | [Validation Policy](validation_policy.md) | [Arch audit](../others/arch-audit.md) | [Tech audit](../others/tech-audit.md)

## What this document is

The [roadmap](roadmap.md) says what each v88 ticket must achieve.
This companion says *why the problem exists*, *what mental model to hold*, and *where the
code actually lives*. It is explanatory, not authoritative: if this document and the
roadmap disagree, the roadmap wins.

Read the roadmap ticket first, then the section here.

**This page deliberately carries no second set of schedulable classification rows.** Formal
band, tier, worktree, merge-position, dependency, slot-ownership, and validation-station
metadata live in the roadmap and only there. The conceptual notes here may explain why an
ordering or resource relationship exists, but only the roadmap states its current scheduling
value or status. The `scripts`-side enforcement checks section *coverage* (one context section
per open roadmap ticket, with no orphans), rejects copied classification rows, and rejects
prose claiming a roadmap-open dependency is closed.

It covers every open v88 ticket entry plus the post-v88 entries. Closed tickets are not
described here; their closure evidence lives in [CHANGELOG.md](../../CHANGELOG.md).
The SA167a name appears only in the shared conceptual umbrella below so its completed handoff
is explained without creating a closed-ticket section.

---

## The mind map

The open release work is one principle with four failure modes. Every ticket is a leaf.

```text
                  ONE FACT, ONE HOME
                  ─ and when the home cannot be read, STOP ─
                                  │
            ┌─────────────┬───────┴───────┬──────────────┐
            │             │               │              │
        DUPLICATED      SILENT         UNOWNED       UNENFORCED
         AUTHORITY     FALLBACK       LIFECYCLE       POLICY
            │             │               │              │
            SA160         SA165          SA161          SA172
            SA174         SA152                         SA175
              │             │               │              │
              │             │               │        (policy-text
         (cookies,      (state/tool     (dead code)    assertions,
          watchlists,    fallbacks,                    file-group
          command sets,  silent skips)                 coherence)
          RLS docstring)
```

**The one sentence:** *Every fact should have exactly one home, and every consumer should
read it from that home. When a consumer cannot read it, the system should stop, not guess —
and the gate that proves all of this must itself actually run.*

That last clause is what the revised priority model added. Auditing the gate layer found
an enforcement failure underneath the four open failure modes; the gate-layer prerequisite
and SA162 correction are now complete, with their evidence archived in the changelog.

| Failure mode | What it looks like | Tickets |
|---|---|---|
| **Duplicated authority** — the same fact is written down in two or more places, so they drift | one CSRF parser copied into two components; one privileged-command set with four owners, one of which claims to be the only one; two hand-rolled file locks remain a bounded structural watch question | SA160, SA174 |
| **Silent fallback** — a component cannot find the authoritative answer, so it substitutes a plausible one and continues | The closed SA150 stopped the explicit-wheelhouse → manifest fallback; SA165's retained state-read and isolation-skip corrections await a final-candidate release verdict; SA152 still carries an independent green-by-absence path | SA165, SA152 |
| **Unowned lifecycle** — a resource is created but nobody is responsible for its identity or destruction | dead code nobody deletes | SA161 |
| **Unenforced policy** — a rule exists only in a human's head | RLS gates assert a policy exists but never what it says; "these two files belong to one contract" is knowledge no artifact holds | SA172, SA175 |

The `scripts/test_*.py` conformance population now has an owning registered execution
context. Its closure evidence is archived in [CHANGELOG.md](../../CHANGELOG.md), so the
scope allowlist, gate registry, parity, and quality-baseline suites run through the same
declared gate layer they protect.

The gate-layer closure evidence, including the current scripts census, registry projection,
hosted job closure, and isolation Make entrypoint, is archived in [CHANGELOG.md](../../CHANGELOG.md).

---

# Bounded independent fixes

Each has a small, well-understood blast radius and remains bounded to its stated concern.

<!-- The detailed stale-lock rationale is archived in CHANGELOG.md.

```python
# historical code shape archived
if _is_stale(path):        # stat: who holds it, how old is it
    path.unlink()          # act: take it away
```

Between those two lines the world can change. Two backup runs both stat the same abandoned lock,
both conclude it is stale, both unlink it, and both then create their own lock file. Each believes
it is the exclusive holder. The lock file still exists, so nothing looks wrong.

The repository owns **two** hand-rolled implementations of this shape — the DR backup lock and
`advisory_lock.py` — and both carry it.

### Why the fix is a shape change, not a patch

Adding another check does not help: any sequence of *check* then *act* has the same window. The fix
is to make reclamation one operation. `flock` gives that directly — the kernel serializes the
critical section, and the stale decision happens with the lock held. `os.rename` or `O_EXCL`
creation keyed on the observed lock identity gives it too, at the cost of more code.

### Why the test is cheap here

This is one of the rare races that is deterministic to reproduce: a two-thread barrier parked
exactly between the stat and the unlink turns the window into a certainty rather than a probability.
No stress loop, no flake hunting — which is why this ticket carries an ordinary red-before /
green-after obligation rather than the softened evidence policy SA170 needed.

### The boundary

The audit's structural question — why two hand-rolled locks exist at all — is deliberately **not**
in scope. Fixing the shape twice is bounded; unifying them is a design change that would widen a
band-C ticket into an architectural one.

-->

---

## SA172 — Make `apply_force_rls`'s idempotency claim true

### The mental model

PostgreSQL row-level security is switched on per table by a small SQL sequence: enable RLS, force it
(so even the table owner is subject to it), then create the policies that say which rows a session
may see and write. `apply_force_rls` runs that sequence and its docstring says it is **idempotent** —
safe to run twice.

It is not. PostgreSQL has no `CREATE POLICY IF NOT EXISTS`, so the second run raises
`42710 duplicate_object` and aborts the migration that called it.

### Why nothing is broken today

Exactly one caller re-applies: `refresh_force_rls_policies`. It calls `revert_force_rls` first, and
the reverse SQL correctly uses `DROP POLICY IF EXISTS`. So the only path that could hit the defect
already avoids it — by accident of ordering, not by contract.

The hazard is the next module migration. Its author reads "idempotent", calls the helper on an
already-enrolled table, and the migration fails in production rather than in review.

### The two honest resolutions

Either make the documentation match the code (say it is not idempotent and must be preceded by
`revert_force_rls`), or make the code match the documentation by prefixing the forward template with
the same `DROP POLICY IF EXISTS` pair the reverse template already carries. The second is two lines
and leaves the repository with a true contract instead of a warning, which is why the acceptance
criteria prefer it while permitting either.

### The assertion that is missing is a separate concern

The conformance gates check that a policy *exists* — `relrowsecurity` and `relforcerowsecurity` true,
and at least one row in `pg_policies`. A table carrying a permissive `USING (true)` policy would pass
every isolation check the repository runs. That gap is real, but it is a tooling improvement over the
whole enrolled-table set rather than a repair of the idempotency claim, and it is carried separately
so this ticket stays the size of its defect: prefix the forward template, prove the contract by
applying twice, done.

### The watch item folded in

`refresh_force_rls_policies` derives each table name from the Django default convention and drops
any name it cannot resolve, silently. All 21 enrolled tables happen to match the convention today,
so this is latent rather than live — but the moment an enrolled model declares its own `db_table`,
its policy refresh becomes a no-op with no warning, on the most security-critical helper in the
tree. The model's real table name is available from `apps.get_model(...)._meta.db_table`, which the
sibling conformance helper already uses.

---

## SA160 — Share one correct CSRF-token helper in the React theme

### The mental model

Django's CSRF protection needs the SPA to read the `csrftoken` cookie and echo it in an
`X-CSRFToken` header. `document.cookie` is a single flat string, and **cookie names are not
unique in it** — the same name can appear more than once at different domain scopes.

Any parser that assumes uniqueness is a latent bug waiting on a deployment topology.

### The concrete defect

Eleven identical lines appear twice — `themes/showcase_react/src/hooks/useApi.ts:20-28` and
`src/components/forms/FormRenderer.tsx:206-211`. Both split `document.cookie` on
`"; csrftoken="` and accept the result **only when it yields exactly two parts**.

Two `csrftoken` cookies yield three parts. So:

```
getCsrfToken() → ''
   → buildRequestHeaders (:89-94) skips X-CSRFToken
      → Django rejects every POST/PUT/PATCH/DELETE with 403
```

GETs keep working. **The app looks alive and merely refuses to save**, and no error names
the cause.

### Why the trigger is ordinary, not exotic

An `app.example.com` deployment alongside a `.example.com` cookie. That is the outcome of
setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or
of a stale apex-scoped cookie in one user's browser. This is the internet-facing generated
project — deployment reality #3.

It **fails closed**: availability, not a security hole. That is why it is Tier 2 and not
higher. But there is no shared helper, no fetch interceptor, and no template-injected
token, so **no layer-up guard exists** — every call site is on its own.

### Implementation shape

One helper in `src/lib/`, following Django's own documented `getCookie`: split on `'; '`,
**match the name exactly**, `decodeURIComponent` the value. Iterate; never count segments.
Both call sites import it, and **no third variant remains** — the duplication is half the
finding.

A `vitest` table test over `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`,
`'csrftoken=A'`, `''` — first three non-empty. The first case is the one that is red today.

Note the tech audit records "no `src/lib/http` seam" as a structural smell; this ticket
creates that seam. Place the helper accordingly.

---

## SA161 — Remove the dead `get_client_ip` definitions from generated settings

### The mental model — the Django fact that makes this dead code

`django.conf.settings` copies **only uppercase names** off the settings module. A
lowercase function defined in `settings/base.py` is not reachable as
`django.conf.settings.get_client_ip`. It never was.

### The concrete defect

`templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both
define a module-level `get_client_ip(request)`. The production copy **rebinds** it under a
comment claiming the rebind exists *"so that production defaults … are actually in effect
at request time"*.

That comment is the actual defect. The code is merely dead; the comment asserts a mechanism
that does not exist, and a future reader will trust it. Grep across all templates returns
only the two definitions — nothing calls either.

The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads
the **uppercase** `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is
correct.

### Implementation shape

Delete both, or leave each as a comment pointing at the orgs helper. **Either way remove the
misleading behavioural comment at `production.py.j2:119-122`** — that is the part that must
not survive.

Keep unchanged: the uppercase settings themselves, and the `REST_FRAMEWORK["NUM_PROXIES"]`
recomputation. Both are live.

Assert with a test that proxy-aware client-IP resolution is unchanged — this touches
security-relevant settings, and "it was dead code" is a claim that deserves proof.

### Emission parity

This edits generated-project templates, so the SA90 emission-parity fixture needs a
  rebaseline with per-file rationale, following the established emission-parity convention.

---

## SA174 — Correct the false SSOT claim on the privileged-command set

### The mental model — a contract with two endpoints and four declarations

A generated project decides, at boot, **which database role serves traffic**. The launcher sets
`QUICKSCALE_PRIVILEGED_COMMAND` as an inline prefix; the settings module reads it and hands back
either the superuser `DATABASE_URL` or the restricted `RUNTIME_DATABASE_URL`; the `orgs` module
reads it too, and skips its RLS boot guard when the value is sanctioned.

That is one contract with two endpoints. It is written down four times.

### The four declarations, and what each one decides

| Station | Role | Upgrade class |
|---|---|---|
| `templates/project_name/settings/production.py.j2:185` | **validator** — selects the role | **frozen** into the user's project at generation vintage |
| `quickscale_modules/orgs/.../apps.py:36` | **guard bypass** — `ready()` returns before `_check_rls_role()` | upgradable, module wheel |
| `quickscale_cli/.../development_commands.py:44` | **producer** — decides whether to inject the env var | upgradable, CLI wheel |
| `quickscale_core/tests/test_generator/test_templates.py:4278` | **oracle** — a literal string transcribing the first station's source text | repo-only |

`templates/start.sh.j2:50,61` is a fifth by inline literal.

### Why this is worth a ticket when nothing is currently broken

All four sets hold `{"migrate", "createcachetable"}` and every divergence direction **fails closed**.
The tech audit adjudicated exactly that question and recorded no defect. So the honest framing is
not *"this is a bug"* but *"this is a structure that already produced silent drift and has no
detector."*

Two facts carry it. First, `apps.py:52` states that its frozenset *"is the single source of truth
for which values are sanctioned"* — **false when written, and still false.** A governance comment
claiming exclusivity beside three other copies is worse than silence, because it stops the next
reader from checking. Second, the CLI copy arrived in `3523f9f8` under the message
*"test: add installed-wheel lifecycle e2e"* — a test-labeled commit that minted a new production
decider on the privilege seam. Nobody reviewed it as such, and no gate noticed.

### The contrast that proves this is not inherent

The **sibling** contract in the same file is single-owner and coherent:
`_KNOWN_NON_DB_COMMANDS = frozenset({"collectstatic", "compilemessages"})` at
`production.py.j2:186` is defined **once**, and its only producer is `Dockerfile.j2:191` — both
template-side, both frozen at the same vintage, so they cannot drift. Same file, same release, same
pattern. The privileged set is the one that grew extra owners.

### What the 2026-08-31 permanence decision did to this ticket

The sanctioned set was settled as **permanent at two commands**, `{"migrate", "createcachetable"}`.
With the set frozen, the drift this ticket existed to prevent cannot occur, so the structural work
collapses and only the false instruction remains. The consolidation plan — rendering the set through
the `runtime_pins` seam, replacing the transcribing oracle with a deriving one, and rebaselining
emission parity — is **archived unimplemented** in the changelog, and is reinstated only if the
watchlist trigger fires: a third sanctioned command, or any two stations disagreeing.

### The shape of what is left

A comment correction. `apps.py:34-52` must say what is true — that this frozenset is one of four
independent fail-closed declarations, that it is **not** a single source of truth, and that adding a
sanctioned command means updating all four stations, named. The arch audit demotes the finding from
rank 1 to a watchlist item with that trigger armed, and does not close it.

### The one thing that must not be simplified away

The `orgs` module keeps its **own independent fail-closed guard**. Collapsing to a single decider —
letting settings be the sole authority and having the module key off a published outcome — looks
tidier and is a recorded sound decision to reject: it deletes the module's independent backstop and
requires a runtime handshake that does not exist. Reading one declaration is not the same as trusting
one decider.

### Emission parity

**None is owed.** No emitted byte changes and no declaration moves, so no generator run and no SA90
emission-parity rebaseline is required. That is what took this work out of the ordered rebaseline run.

---

## SA175 — Assert disposition coherence for the launcher↔settings contract

### The mental model — a taxonomy that classifies files, for a problem that is about pairs

Beta migration decides, for every emitted path, whether an upgrade **carries the user's copy
forward** or **replaces it with the new one**. The decision is recorded per file, across seven
hand-authored categories, and a conformance test proves every emitted path lands in one of them.

That test asks *"is this file classified?"* It cannot ask *"do these files still agree?"* — because
nothing anywhere records that two files belong to one contract.

### The concrete split

The privileged-command contract lands on **both sides** of the line:

- `settings/production.py` — the **validator**, holding the fail-closed privilege guard — sits in
  `FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES` (`beta_migration.py:59`) and
  `FRESH_FIRST_DONOR_DJANGO_FILES` (`:92`). It is copied **from the donor**: the user's existing
  project wins over the freshly generated one.
- `start.sh` and `Dockerfile` — the **producers** of the env vars that file validates — sit in
  `IN_PLACE_INFRASTRUCTURE_TARGETS` (`:109,121`) and
  `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS` (`:125,128`). They are copied with substitution at
  the **new** vintage.

Producer new, validator old. Membership is perfect; coherence is unexamined.

### Why the donor-wins choice is not the defect

It is defensible on its own terms, and this work must preserve it: `settings/production.py` is where
users put their real deployment configuration, and overwriting it would be worse than carrying it
forward. The defect is that the *pairing* is invisible — the split is a decision nobody made, sitting
in a place that cannot express it.

### Scope discipline — this is one assertion, not a redesign

The deferred finding behind this has two real options: derive the taxonomy from generator emission,
or emit a versioned ownership manifest supporting vintage negotiation against the `project_contract`
version that already exists in state. **Neither is in scope.** Both stay behind the growth trigger —
a third generated-project consumer, a public updater, an emitted-file expansion, or a second theme —
and the blast radius stays small meanwhile because `quickscale_devtools` is maintainer-only, excluded
by name from the publish scripts.

What is in scope: name the contract's three participating paths once — `settings/production.py`,
`start.sh`, and `Dockerfile` — in this work's own assertion, and assert that members of one named
group cannot take dispositions from opposite families. There is no single upstream declaration to
source them from, because the command set was settled as permanent rather than consolidated. One
assertion, one named group, and a red-then-green proof.

---

## SA165 — Discharge the tech-audit watch items that carry an action

### The retained product boundary

The accepted A-C product object `573a57a34301e6a91971a7845095bd913bebd5e1` addresses four
action-bearing audit notes. State consolidation raises on corrupt and non-mapping YAML roots before
writing; the isolation gate authorizes empty-parameter skips by the two intended test identities;
the host-dependent emission exception records why `.env` is exceptional and when the list must be
derived; and generated operations guidance rejects predictable local credentials in shared
environments.

Those product bytes are retained and are not reopened by the documentation closeout. The remaining
obligation is evidentiary: a release verdict must cover the settled Phase D bytes. The only green
release run happened before the final `CHANGELOG.md` edit, so it is useful historical evidence but
not acceptance of the current candidate. The replacement run is now expressly authorized as `EV-8`;
until it returns green over the frozen candidate, this section and the four audit notes remain live
and no closure is claimed.

### Why the distinction matters

A release verdict is evidence about exact bytes, not about an intention or an almost-identical
candidate. Reusing the earlier exit 0 after a status file changed would turn the finality guard into
a prose assertion. The roadmap retains the executable continuation, plan authority, and exact
handoff; this companion retains only the conceptual boundary between accepted product work and the
still-pending closeout.

---

## SA179 — Reconcile the retained documentation and retire the four audit notes

### The mental model

A release verdict is evidence about **exact bytes**. The repository's standing rule is that a
ticket's evidence must cover its own settled candidate, which is what caught an earlier
stale-but-green run.

That rule interacts badly with a candidate that contains the documents used to *record* reviews. The
planner, the docs hub, the ticket-context page, the changelog, and the executable consistency test
are precisely where a passing review gets written down. When they sat inside the frozen set, writing
"the review passed" edited a bound blob and invalidated the review being recorded. Two cycles were
spent on that loop before the shape was named.

### What separating them buys

A candidate made only of product bytes cannot be disturbed by recording its own result. The
documentation reconciliation then becomes ordinary work with an ordinary gate — the consistency
suite — rather than something needing a frozen-byte review it can never survive.

### Why the four notes cannot be retired early

`flush_empty_consolidated_sections` failing hard, the identity-bound isolation skip,
`_HOST_DEPENDENT_PATHS` accountability, and the generated local-credential warning are all
**implemented** in retained product bytes. The tech audit nevertheless holds each note live *until a
release verdict covers the settled candidate*, because an implemented change with no verdict over it
is an intention, not an accepted fact. Retiring a note before that verdict returns green would put a
claim in the audit that no evidence supports — the exact failure the rule exists to prevent.

### What this ticket is not

It carries no product behaviour and touches no code under the generator, the core package, or
`scripts/`. That is deliberate and load-bearing: a documentation ticket that also edited product
files would re-create the entanglement it exists to remove.

---

## SA178 — Restate the arch-audit watchlist and correct the `trigger_inputs` name

### The mental model

A watch item is a bet: *"this is not a problem yet, and here is the trigger that would make it
one."* The bet is worthless if the trigger is lost, and it is worse than worthless if a later pass
restates a **superseded** version of the list, because the audit then carries conclusions nobody
re-derived. Restating is therefore the work; removing is not.

### 1. `trigger_inputs` has drifted from its name

`check_gate_parity.py:2652-2690` uses the field as a **bidirectional partition of `e2e.yml`'s path
allowlist**, not as *"what changes should trigger this gate"*. That is why `check-core-compat`'s
trigger reads `quickscale_modules/backups/**`.

**Not a defect** — the check it performs is real and exact. It is a name that lies about a correct
mechanism. It becomes load-bearing the moment a gate is ever *skipped* on the basis of
`trigger_inputs`, because then the name's meaning and the field's meaning diverge in production.

Rename it, or record the actual semantics plus that promotion trigger in the docstring and schema
description.

### 2. The three that are not fired

The **current** three, not the superseded pre-resolution list: the two hand-pinned literals minted
inside the new provisioning derivation (`provision_ci_postgres.sh:93,96` — `!= teams` and `== 12`,
re-introducing a module name and a module count into a script whose whole point is deriving them);
the second copy of the PostgreSQL major (`provision_ci_postgres.sh:15` against `runtime_pins.py:30`,
two values that are arguably correct because the repo toolchain and the generated project are
genuinely independent); and the roughly six count-pinned oracles in `scripts/test_gate_parity.py`.

Each is not fired, each fails loudly, and each has a written trigger. Note the shape: all three were
**created by a fix**, which is the ordinary cost of centralization and the reason the fix-regression
question is asked every pass.

### Why this is documentation and nothing else

No gate changes behaviour here. Nothing is closed. The value is that the next audit pass inherits an
accurate list instead of re-deriving one, and that a correct mechanism stops carrying a misleading
name.

---

# Post-v88 — recorded backlog

These four are in the roadmap so the findings are not lost. Listing a sub-item here does not
authorize implementing it.

## SA177 — Assert RLS policy predicate text, not just policy existence

### The mental model

Row-level security is only as strong as what the policy *says*. The repository's isolation and
conformance gates currently prove that a table has RLS enabled, RLS forced, and at least one row in
`pg_policies`. None of them reads the policy predicate.

So a table carrying a permissive `USING (true)` policy — the classic way RLS is accidentally
neutered — passes every isolation check the repository runs. The tenancy model's actual invariant is
a split: writes are scoped to the current organization, while reads may cross tenants **only** when
an operator flag is set, and that read policy is deliberately `FOR SELECT` so operator access can
never become write or delete visibility. Today that split is enforced by a code comment.

### Why comparing text is the right shape

The rendered template is the specification, and `pg_policies` stores what the database actually
believes. Comparing the stored `qual` and `with_check` text against the rendered template for each
enrolled table turns the comment into a gate, and it fails loudly on any drift rather than degrading
silently.

### Why it is not in v88

It needs a live PostgreSQL, an enrolled-table walk, and a proof step that weakens a predicate to
observe red and then restores exact bytes. That is a materially larger unit than the two-line
forward-template repair it was bundled with, and it improves tooling rather than fixing the defect
that repair addresses. It should be pulled forward the moment the policy templates are edited again,
because that is when drift becomes likely rather than theoretical.

---

## SA152 — Refresh the beta-migration maintainer targets

The 2026-08-21 audit found the **mechanics current**: the Makefile flag surface (`DONOR`,
`RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()`, every
command in `VERIFICATION_COMMAND_SPECS` still exists, and the file-ownership taxonomy is in
sync and enforced by 7 passing conformance tests. So this is not a rot ticket. Four residual
gaps:

- **The SA151 collision is now a settled prerequisite.** The workflow's verification stack runs
  `quickscale manage migrate` against a recipient that may carry an existing database. SA151's
  clean-break implementation makes a **fresh database the only upgrade path**, invalidating the
  in-place workflow's implicit assumption; SA152 must reconcile that mismatch in its own scope.
- **No end-to-end exercise.** The targets appear in no CI workflow and no
  `scripts/gate_registry.json` entry. Coverage is unit-level taxonomy conformance only, so
  breakage surfaces for a maintainer **mid-migration** — the worst possible moment.
- **Silent skip in the conformance gate.** `_template_emitted_paths()` calls
  `pytest.skip()` when the template tree is not found, so a path-resolution regression turns
  the ownership gate **green instead of red**. Same silent-fallback family as the closed SA150 and
  the discharged state-read and isolation work.
- **Stale doc provenance.** `beta-site-migration.md` is headed *"shipped in v0.81.0"*
  against `VERSION` 0.87.0, and describes the tool as *"backed by Python scripts under
  `scripts/`"* when `scripts/beta_migrate.py` is an eight-line wrapper over
  `quickscale_devtools`.

## SA153 — Close the property-portal basics gap in `listings`

**A high-value post-release work item**, driven by the planned `buenosairesproperties.com`
migration. The framing that matters: the gap is **not module existence**. `listings` ships a
deliberately generic `AbstractListing` plus a concrete `Listing`, and `blog` is
substantially complete. The gap is **property-vertical depth and public presentation**, and
every sub-item is a *basic* — a real-estate portal cannot launch without it.

The structural problem underneath most of the sub-items: the documented extension answer is
**subclassing `AbstractListing`**, but `views.py`, `urls.py`, `admin.py`, and `ListingFilter`
are all bound to the **concrete** `Listing`. So subclassing today yields a model and an admin
base but **no working public views, URLs, or filters** — the Tier 2 abstract-model contract
in [module-extension.md](module-extension.md) is half-delivered.

Two project constraints bind every sub-item:

- **Every new child table carries its own `organization_id` column** with its own RLS policy
  — the locked Option C child-table policy in [decisions.md](decisions.md). No parent-join
  RLS, including for `ListingImage`.
- RLS-boundary coverage must match the existing `test_rls_boundary.py` pattern.

Sub-items: image galleries, property attributes, attribute filtering + keyword search
(the module README currently **claims** search that does not exist), multi-currency (a
hardcoded `$` against a single-currency `DecimalField`), i18n (`USE_I18N = True` with no
`LocaleMiddleware`, no locale dirs, no marked strings), themed public presentation,
listing-linked lead capture into `crm`, SEO (no sitemaps, no `robots.txt`, no Open Graph
anywhere in the tree), and a public JSON read API.

## SA154 — Property-portal optional capabilities

An inventory of optional capabilities, not an implementation instruction. Map/geocoding,
saved searches and match alerts,
agent/office profiles, portal syndication feeds, virtual tours, featured placement tied to
the `billing` credits ledger, blog↔listing cross-linking, and PostgreSQL `SearchVector`
full-text search.

Each sub-item needs its own acceptance criteria if it is promoted, or a written rationale if it
is dropped.

---

## Reusable reasoning traps

Worth holding as a set, because each appears in more than one ticket:

- **The tautology trap**. A test that reads the authoritative value and asserts the
  authoritative value passes for any value, including nonsense. Derive *wiring* assertions;
  keep *negative controls* literal.
- **The green-by-absence trap** (SA152, with SA165's retained fixes as the pending closeout example). Skipping, filtering,
  and unresolvable paths all produce green. Every one of them must be made to produce red.


---

## SA167a / SA167c — module wiring standardization

This shared umbrella retains historical context for the module-wiring standardization. The completed
SA167a, SA167b, and SA167c handoffs are archived in [CHANGELOG.md](../../CHANGELOG.md). SA167c's
phases A-E remain accepted on retained product object
`91fd3bb6e6b638735361b511c1515cddccce5d15`; its sole Phase-F release verdict under `EV-7` exited 0 on frozen
base `21a33fbf22b033cab07ba63b592e21b999667fb2`, with all twelve CI stages and both E2E lanes
green. Merge position #21 is retired.
SA167d's completion-grade Phase C is archived as a conditional post-integration candidate;
exact-tip integration remains pending. SA165 remains open as an integrated retained partial with
`deps: none`; SA165-R1 remains tracked. Ticket metadata
lives in the [roadmap](roadmap.md), not here.

SA170's later ordered serial and concurrent campaigns both passed; their final acceptance and the
earlier retained-partial history are archived in [CHANGELOG.md](../../CHANGELOG.md). Current
dependency metadata remains in the roadmap.

**The concept.** A QuickScale module is two things stacked. Underneath is an ordinary
Django app — `apps.py`, models, migrations — with no QuickScale divergence at all.
On top is one QuickScale-specific thing: the *adapter*, which is the machine-readable
form of the install instructions a normal Django library writes in its README.
Django assumes a human reads "add this to `INSTALLED_APPS`" and types it; `quickscale
apply` generates the project, so that instruction has to be data.

**What went wrong.** That one fact — which Django apps a module contributes — had five
competing representations at kickoff: a wiring projection in six manifests, a Python literal
inside core for five more, nothing at all for `social`, an inert `django_apps:` key in eleven
manifests that no code reads, and a per-module function pair in the CLI. SA167a's implementation
and accepted root quality-gate oracle are recorded on the integration branch:
all five former core literals now come from their own manifest projections. SA167b subsequently
moved every module: P1/P2 relocated analytics, backups, blog, forms, listings, and notifications,
and P3 relocated auth, orgs, and storage, leaving no per-module block in core. Its P4 acceptance
then confirmed the twelve module-owned adapters, generic-only core registry, restoration behavior,
and unchanged emission parity; the accepted boundary is merged integration-branch state. When a fact
lives in five places, no one can tell which is the answer, and `social` shipped models
and a migration that no generated project ever installed.

**The rule** is now written in
[decisions.md §Module Wiring Authority](./decisions.md#module-wiring-authority): every
module owns its adapter, and declares its apps once, in its own `module.yml`. The retained
module-wiring product bytes make the tree match it: declarations and adapters now live with their
modules, the inert key is retired and its gate bytes are retained, and the CLI boundary is drained. The
archived SA167c checkpoint and green Phase-F verdict reflect release validation and integration
state, not a product-contract rollback.

**Why the split is by phase and not by module.** All nine core-side blocks began in one
1,508-line file, and every phase has had to edit that same file. The phase boundary keeps one
logical adapter migration understandable without turning it into nine separate conceptual sections.
