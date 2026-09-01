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
           SA160         SA165           SA161          SA166
           SA164         SA152           SA161          SA172
           SA172         SA172           SA170          SA175
           SA174           │             SA171            │
             │             │               │        (testimony
       (cookies,      (state/tool     (DB, locks,      trail,
        watchlists,    fallbacks,      dead code,    policy-text
        command sets,  silent skips)    Docker)      assertions,
        RLS docstring)                              file-group
                                                     coherence)
```

**The one sentence:** *Every fact should have exactly one home, and every consumer should
read it from that home. When a consumer cannot read it, the system should stop, not guess —
and the gate that proves all of this must itself actually run.*

That last clause is what the revised priority model added. Auditing the gate layer found
an enforcement failure underneath the four open failure modes; the gate-layer prerequisite
and SA162 correction are now complete, with their evidence archived in the changelog.

| Failure mode | What it looks like | Tickets |
|---|---|---|
| **Duplicated authority** — the same fact is written down in two or more places, so they drift | one CSRF parser copied into two components; one privileged-command set with four owners, one of which claims to be the only one; two hand-rolled file locks with one shared race | SA160, SA164, SA171, SA174 |
| **Silent fallback** — a component cannot find the authoritative answer, so it substitutes a plausible one and continues | The closed SA150 stopped the explicit-wheelhouse → manifest fallback; a corrupt state file still returns silently; a skip where a failure belongs | SA165 |
| **Unowned lifecycle** — a resource is created but nobody is responsible for its identity or destruction | a fixed-tag Docker image outside the scope contract; dead code nobody deletes | SA161, SA170 |
| **Unenforced policy** — a rule exists only in a human's head | no requirement that a behavioural commit leave a trail; RLS gates assert a policy exists but never what it says; "these two files belong to one contract" is knowledge no artifact holds | SA166, SA172, SA175 |

The `scripts/test_*.py` conformance population now has an owning registered execution
context. Its closure evidence is archived in [CHANGELOG.md](../../CHANGELOG.md), so the
scope allowlist, gate registry, parity, and quality-baseline suites run through the same
declared gate layer they protect.

The gate-layer closure evidence, including the current scripts census, registry projection,
hosted job closure, and isolation Make entrypoint, is archived in [CHANGELOG.md](../../CHANGELOG.md).

---

# Bounded independent fixes

Each has a small, well-understood blast radius and remains bounded to its stated concern.

## SA171 — Make stale-lock clearing atomic in both file locks

### The mental model

A "stale lock" reclaim is a decision followed by an action:

```python
# _lock.py:119-137 — the check and the act are two separate syscalls
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

### The assertion that is actually missing

The conformance gates check that a policy *exists* — `relrowsecurity` and `relforcerowsecurity` true,
and at least one row in `pg_policies`. A table carrying a permissive `USING (true)` policy would pass
every isolation check the repository runs. Comparing the stored `qual` / `with_check` text against
the template turns the operator-read / tenant-write split from a comment into a gate, and it is the
natural place to prove whichever idempotency contract is chosen.

### The watch item folded in

`refresh_force_rls_policies` derives each table name from the Django default convention and drops
any name it cannot resolve, silently. All 21 enrolled tables happen to match the convention today,
so this is latent rather than live — but the moment an enrolled model declares its own `db_table`,
its policy refresh becomes a no-op with no warning, on the most security-critical helper in the
tree. The model's real table name is available from `apps.get_model(...)._meta.db_table`, which the
sibling conformance helper already uses.

---

## SA170 — Give the E2E Docker harness a closed resource contract

### The mental model

Every E2E resource this project creates is stamped with a **scope** — a unique string minted once
per run — and every cleanup reclaims resources by asking Docker "give me everything labelled with
this scope". Nothing is found by name. That is what lets two runs share one Docker daemon without
touching each other's containers, and what lets cleanup be exhaustive without guessing.

The design holds everywhere except two places, and both stalled a phase of another ticket for
several passes. Understanding why they stalled it is the point of this ticket.

### Why the symptoms looked like flakes

A flake is a failure that appears and disappears without the code changing. Both symptoms here —
a container that could not be found, and a build that ran out of time — have that surface.
Underneath, neither is random:

**Shared mutable name.** One test builds its Docker image under a hardcoded tag instead of a
scoped one, and deletes that tag when it finishes. Two runs on one machine therefore reach for the
same object, and whichever finishes first deletes it out from under the other. The collision needs
two runs to overlap, so it looks like chance — but it is a missing scope, not a race.

**A budget that measures the machine.** The same test allows five minutes for a Docker build. A
warm build takes seconds because Docker reuses cached layers; a cold one recompiles a frontend and
installs a database client. Whether five minutes is generous or insufficient depends on the cache,
not on the code. Re-running it on a warm machine will pass forever and prove nothing.

### The finding that actually explains the stall

The third defect is the reason the first two were never diagnosed.

The helper that waits for a container to start asks Docker for containers *whose name contains* a
string — a substring match, not an exact one — and asks for **all** containers, including ones that
have already died. It then decides "is it running?" by looking for the word `up` somewhere in the
reply. A container that crashed one second after starting does not produce that word, so the helper
concludes "not ready *yet*" and keeps waiting. Forty seconds later it reports *"the container did
not become running in time"* — which is true, and useless. The crash and its exit code are never
shown.

So the harness's failure report cannot distinguish **"still starting"** from **"already dead"**.
That is why repeatedly re-running the suite produced greens that taught nobody anything: on the runs
that did fail, the harness had already thrown away the reason.

### Why the old acceptance criterion could not be met

The blocked phase required *red-before / green-after* evidence: show the failure happening, apply
the fix, show it gone. That is the right standard for a deterministic defect. It cannot be met for a
collision between two runs that must be scheduled to overlap, and it cannot be met for a timeout
whose outcome depends on cache state.

The resolution is not to lower the standard. It is to **apply it one level down**, where the
behaviour *is* deterministic: the readiness decision is a pure function of a status string, so it
can be fed a crashed container's status and shown to answer wrongly today and correctly after; and
whether cleanup can see an image is a labelled-resource query, which either finds it or does not.
Both give genuine red-before/green-after evidence in milliseconds, with no flake to reproduce.

### The reasoning trap this illustrates

*Re-running a test is evidence about the test's environment, not about the code.* When a suite keeps
passing but a failure is known to exist, the useful question is not "how do I make it fail again"
but "what would this harness have told me if it had failed" — and if the answer is "nothing
specific", that is the first defect to fix.

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

## SA174 — Give the sanctioned privileged-command set one owner

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

### Implementation shape — reuse the seam that already exists

`generator/runtime_pins.py` already does this job for Python, Django, and PostgreSQL versions: one
declaration, rendered into templates through `generator.py:521-526`, read by tests rather than
transcribed. Put the command set there.

The emitted copy **stays** — a generated project must render standalone with no import back into
QuickScale, and "100% yours, no vendor lock-in" is the product's central promise. What changes is
its status: a *rendering* of the declaration rather than a restatement of it. The CLI and module
copies, which ship on the same release line as core, become imports. The oracle stops matching a
literal and starts comparing the rendered set against the imported ones — the same move made for the
planning documents when literal ticket IDs were replaced by derived counts.

### The one thing that must not be simplified away

The `orgs` module keeps its **own independent fail-closed guard**. Collapsing to a single decider —
letting settings be the sole authority and having the module key off a published outcome — looks
tidier and is a recorded sound decision to reject: it deletes the module's independent backstop and
requires a runtime handshake that does not exist. Reading one declaration is not the same as trusting
one decider.

### Emission parity

This changes emitted bytes, so the SA90 emission-parity fixture needs a rebaseline with per-file
rationale, following the established convention and preserving every prior `baseline_evidence` entry.

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

What is in scope: name the contract's participating paths once, sourced from the single declaration
rather than re-listed, and assert that members of one named group cannot take dispositions from
opposite families. One assertion, one named group, and a red-then-green proof.

---

## SA165 — Discharge the tech-audit watch items that carry an action

### The mental model

The tech audit's *Notes* hold thirteen items. Most are **accepted trade-offs** or are owned
elsewhere — the closed SA150 discharged the local-wheelhouse seam, while integration-branch CI,
generator lock generation, the DB-free healthcheck, the
CRM count fallbacks, and non-durable atomic state writes are each recorded as **deliberate
and explicitly out of this ticket's scope**.

Do not re-litigate those. Four items carry a concrete action; this ticket is exactly those
four.

### 1. `flush_empty_consolidated_sections` swallows a corrupt state file

`quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on
`yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []`
markers that downstream readers use to distinguish *"M2 has spoken"* from *pre-M2 state*.

The trigger is narrow — the file was just written successfully by `save()` — but this is
precisely the shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`), and
`tech-audit.md` is the declared SSOT for that class. Same family as the closed SA150, one layer over.

**Raise or report. A regression test must assert the raise, not a log line.**

### 2. The isolation-gate skip allowlist matches on message, not identity

`scripts/test_isolation_conformance.sh:184` keys on
`message.startswith('got empty parameter set')`. That silences an empty parameter set on
**any** of the eleven parametrized tests in `test_tenant_table_conformance.py` — not only
the two `PENDING_REMEDIATION` ones its own comment describes.

A message prefix is not an identity. Narrowing it to the two test names costs one line.
Prove it: deliberately empty the ENROLLED set and confirm the gate turns **red**.

### 3. `_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station

`be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate
(`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound
and the `755`/`644` mode normalization correctly removes a umask dependency.

But this is an **exception list on the repository's strictest gate**. The monotonicity rule
to write down: a second entry deserves scrutiny, a third deserves a derivation. Add the
per-entry rationale and that escalation note — or derive it now.

### 4. Generated local-development credentials are predictable by construction

`generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and
`runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and
`.env.example` — none of which `.gitignore.j2` excludes.

**Safe as shipped**: no published DB port, local dev only, production supplies
`RUNTIME_DATABASE_URL` from the environment. The gap is that it is undocumented. State
explicitly in `OPERATIONS.md` that these credentials must not survive into any shared
environment. Documentation only — do not change the derivation.

---

## SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items

### The mental model

A watch item is a bet: *"this is not a problem yet, and here is the trigger that would make
it one."* A watch item whose trigger **cannot be evaluated** has stopped being a bet and
become debt — it costs a read every audit pass and can never fire.

The watchlist was rewritten by the 2026-08-28 pass: one item's parent finding was resolved, one
item fired and was promoted, and three new ones were minted inside the landed provisioning
derivation. What remains here is one item carrying an explicit action, one naming question that
becomes load-bearing on a specific trigger, and the restatement of the three new items so their
triggers survive the next pass.

### 1. The SA92 migration-squash tuple — artifact found, re-anchor remains open work

The artifact is
`quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, a bounded
literal tripwire for cross-table `UPDATE … SET organization_id` migration DML; it is
not a schema-parity proof. Its `_migdir()` helper reads the inert `django_apps:`
manifest key and silently guesses a conventional path when absent, while its parity
backstop still names the retired `v87` baseline. The current regenerated migrations and
discharged S4 BYPASSRLS prerequisite are settled; SA164 owns the `_migdir()` helper
correction and parity-backstop re-anchoring.

### 2. Privileged-command pair — the watch item fired, and left this ticket

This was carried for two passes as *"values agree, claimed authority does not"*. The 2026-08-28
structural pass re-counted the owners and found **four**, not two — the trigger fired, and the item
was promoted out of the watchlist into a ranked finding. It is no longer adjudication work and no
longer belongs here; **SA174** carries it, with the full census and the chosen shape.

What survives in this ticket is the shape of the lesson, which the remaining items share: a watch
item is a bet, and when the bet resolves, the item stops being a watch item. Restating it here as a
watch item a third time would be the error.

### 3. `trigger_inputs` has drifted from its name

`check_gate_parity.py:2652-2690` uses the field as a **bidirectional partition of
`e2e.yml`'s path allowlist**, not as *"what changes should trigger this gate"*. That is why
`check-core-compat`'s trigger reads `quickscale_modules/backups/**`.

**Not a defect** — the check it performs is real and exact. It is a name that lies about a
correct mechanism. It becomes load-bearing the moment a gate is ever *skipped* on the basis
of `trigger_inputs`, because then the name's meaning and the field's meaning diverge in
production.

Rename it, or record the actual semantics plus that promotion trigger in the docstring and
schema description.

### And restate the three that are not fired

The **current** three, not the superseded pre-resolution list: the two hand-pinned literals minted
inside the new provisioning derivation (`provision_ci_postgres.sh:93,96` — `!= teams` and `== 12`,
re-introducing a module name and a module count into a script whose whole point is deriving them);
the second copy of the PostgreSQL major (`provision_ci_postgres.sh:15` against `runtime_pins.py:30`,
two values that are arguably correct because the repo toolchain and the generated project are
genuinely independent); and the roughly six count-pinned oracles in `scripts/test_gate_parity.py`.

Each is not fired, each fails loudly, and each has a written trigger. Keep the triggers intact —
restating is the work, not removing. Note the shape: all three were **created by a fix**, which is
the ordinary cost of centralization and the reason the fix-regression question is asked every pass.

---

## SA166 — Require a testimony trail for behavioural commits

### The mental model

Every other ticket in this release makes a *machine* tell the truth. This one makes a
*commit* tell the truth.

### The evidence

`d3d4c633` and `d4b0e834` were both titled **"v0.87.0: QuickScale 0.87.0"** while in fact
changing hosted and publish provisioning. `d3d4c633` also left a repository conformance test
red — a stale publish-parity oracle, since repaired and closed.

Both audits independently flagged the same shape: **a release-shaped message carrying a CI
topology change**. It was read closely only because the arch audit's delta-classification
step treats unlabeled-behavioural commits as read-at-full-depth. Absent that convention, it
would have shipped unexamined — and it did ship a red test.

### Why it is Tier 3

The audit records this as **maintainer-process risk**, not a source finding. The registered
gate layer is an executed context, so this ticket can add its process evidence without
reopening the gate-suite work.

### The design constraint that decides whether this succeeds

*"false-positive cost is measured on the existing history and the rule is narrowed until it
is quiet on legitimate release commits."*

A noisy process gate gets a bypass flag, and a bypass flag gets used by default. Measure the
rule against real history **before** turning it on. If it fires on legitimate release
commits, narrow it — do not add an override.

Scope: a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the
provisioning stations requires a roadmap ticket reference or a `CHANGELOG.md` entry,
enforced mechanically. Registered in `scripts/gate_registry.json`, passing
`scripts/check_gate_parity.py`. Prove it with a deliberately introduced untitled workflow
change, reverted before merge.

---

# Post-v88 — recorded backlog

These three are in the roadmap so the findings are not lost. Listing a sub-item here does not
authorize implementing it.

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
  SA165.
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
- **The green-by-absence trap** (SA152, SA165). Skipping, filtering,
  and unresolvable paths all produce green. Every one of them must be made to produce red.


---

## SA167a / SA167c / SA167d — module wiring standardization

These open roadmap entries carry conceptual context for the module-wiring standardization. The
completed SA167a handoff is retained only as historical context, and SA167b's completed relocation
and P4 acceptance are archived in [CHANGELOG.md](../../CHANGELOG.md). SA167c remains open in
current `v88`: phases A and B are accepted, its Phase-C product delta is retained delivery, and
C acceptance plus phases D-F remain pending. SA167d remains open:
phases A-E are accepted at E0 tip `bd2c291ba2d40494970464741ac51bfd45445a19`; retained-partial
convergence and terminal attestation are complete, and retained-partial-only merge-back is
authorized for the reviewed partial plus the latest-v88 status reconciliation without closing the
ticket. Completion-grade Phase C convergence, terminal attestation, and exact-tip integration
remain pending. Ticket metadata and the remaining closeout handoff live in the [roadmap](roadmap.md),
not here.

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
module owns its adapter, and declares its apps once, in its own `module.yml`. These four
tickets make the tree match it — `a` declares, `b` relocates, `c` retires the inert key
and adds the gate that keeps it true, `d` drains the CLI.

**Why the split is by phase and not by module.** All nine core-side blocks began in one
1,508-line file, and every phase has had to edit that same file. The phase boundary keeps one
logical adapter migration understandable without turning it into nine separate conceptual sections.
