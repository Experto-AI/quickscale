# v88 Ticket Context — Concepts and Implementation Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **v88 Ticket Context**
> **Related docs**: [Roadmap](roadmap.md) (authority for scope, bands, worktrees, merge order) | [Decisions](decisions.md) | [Validation Policy](validation_policy.md) | [Arch audit](../others/arch-audit.md) | [Tech audit](../others/tech-audit.md)

## What this document is

The [roadmap](roadmap.md) says *what* each v88 ticket must achieve and *when* it may run.
This companion says *why the problem exists*, *what mental model to hold*, and *where the
code actually lives*. It is explanatory, not authoritative: if this document and the
roadmap disagree, the roadmap wins.

Read the roadmap ticket first, then the section here.

It covers **all twenty v88 tickets** plus the three post-v88 entries. Sections are ordered
by merge band (A → B → C), which is also the order in which the work becomes safe to do.

---

## The mind map

The whole release is one principle with five failure modes. Every ticket is a leaf.

```text
                    ONE FACT, ONE HOME
                    ─ and when the home cannot be read, STOP ─
                              │
      ┌──────────┬────────────┼────────────┬──────────────┐
      │          │            │            │              │
  UNEXECUTED  DUPLICATED   SILENT      UNOWNED       UNENFORCED
  ENFORCEMENT  AUTHORITY   FALLBACK    LIFECYCLE       POLICY
      │          │            │            │              │
 the gate    the fact is   the answer   nobody owns   the rule is
 doesn't run  written in    is missing   the thing     only in a
 or lies      2+ places     so guess     we created    human's head
      │          │            │            │              │
   SA156      SA137         SA150        SA151          SA123
   SA155      SA134         SA165a       SA142          SA166
   SA157      SA124         SA152c       SA135          SA123
   SA158      SA118           │          SA161            │
   SA159      SA163         (state       SA160          (dep-vuln +
   SA162      SA164a          file)      (dead/dup       security
     │        SA160             │         code)          scanners)
  (base ref,  SA161                                        │
   suites,      │                                       SA166
   oracles,   (paths, pins,                            (testimony
   false-     manifests, CI                             trail)
   greens)    env, cookies)
```

**The one sentence:** *Every fact should have exactly one home, and every consumer should
read it from that home. When a consumer cannot read it, the system should stop, not guess —
and the gate that proves all of this must itself actually run.*

That last clause is what the revised priority model added. The original plan had four
failure modes; auditing the gate layer found a fifth sitting underneath all of them.

| Failure mode | What it looks like | Tickets |
|---|---|---|
| **Unexecuted enforcement** — the gate that proves the other four does not run, or runs on a lie | 10 of 14 `scripts/test_*.py` suites wired to nothing; the quality gate's base ref points at a deleted branch; a test that passes when its tool is deleted | SA156, SA155, SA157, SA158, SA159, SA162 |
| **Duplicated authority** — the same fact is written down in two or more places, so they drift | devtools version pinned by hand; Python/Postgres versions retyped in tests; the SA117 required-path set restated in four places; manifest defaults restated in imperative code; the PGDG install copied across 14 stations | SA137, SA134, SA124, SA118, SA163, SA160, SA164 |
| **Silent fallback** — a component cannot find the authoritative answer, so it substitutes a plausible one and continues | wheelhouse set but no wheel matches → returns the manifest spec; a corrupt state file returns silently; a skip where a failure belongs | SA150, SA165 |
| **Unowned lifecycle** — a resource is created but nobody is responsible for its identity or destruction | E2E images accumulate; the integration gate assumes a PostgreSQL server someone else started; migration history accretes; dead code nobody deletes | SA151, SA142, SA135, SA161 |
| **Unenforced policy** — a rule exists only in a human's head | no dependency-vulnerability or security static-analysis gate; no requirement that a behavioural commit leave a trail | SA123, SA166 |

The worktree grouping follows it directly:

- **W1** — duplicated authority + silent fallback in the **version/dependency/interpreter** domain.
- **W2** — unexecuted enforcement, then duplicated authority + unenforced policy in the **tooling** domain.
- **W3** — unowned lifecycle in the **service and emission** domain.

---

## Why band A goes first (the argument in one page)

Read these four facts together:

1. `scripts/check_quality_baseline_monotonicity.py:305-306` and `:1395-1396` fall back to
   `ref = "v87"`. That branch was retired for `v88` and never existed as a tag.
2. When the fallback fails, the gate exits 2 with `MERGE_BASE_ERROR`, and
   `scripts/check_quality.sh:123` deletes the previous run's report *before* any analyzer
   runs. So `make quality` produces nothing.
3. Of 14 `scripts/test_*.py` suites, **10 are wired to no target at all**. Run under the
   project interpreter, they produce **959 passed, 74 failed**.
4. `scripts/test_check_sa117_scope.py:596-617` asserts `returncode == 2` from a subprocess
   whose script path never resolves. CPython exits 2 on `can't open file`. The test would
   pass if the tool were deleted.

Now read the execution rule every ticket in this release inherits: *"Leave `make quality`
no worse than found."*

That rule has been unverifiable for the entire `v88` branch, and both audit documents
recorded the invariant as enforced. Meanwhile SA124's headline acceptance criterion —
*"`scripts/test_check_sa117_scope.py` covers the divergence failure"* — would have been
written into an unexecuted suite, beside a guaranteed false-green, most plausibly by
copying it.

**Band A is not tidying. It is the difference between shipping tickets and shipping
claims about tickets.**

---

# Band A — Make the gate layer tell the truth

Five tickets, four of them independent and small, one integrating. W2 owns four; W1 owns
SA159 because it edits `scripts/version_tool.sh`, which is SA137's file.

## SA156 — Make the quality gate's fallback base ref resolve

`Band A · Tier 1 · W2 · merge #1 · deps: none`

### The mental model

The quality gate enforces **monotonicity**: quality metrics may not get worse than they
were at the merge base. That requires knowing what the merge base *is*, so the gate walks a
precedence chain to find a reference:

```
QUALITY_BASELINE_BASE_REF  (explicit override)
   ↓ unset
GITHUB_BASE_REF            (hosted PR target — probes origin/<ref> then <ref>)
   ↓ unset
"v87"                      (hard-coded fallback — probes the bare name only)
```

Every link but the last is fine. The last one names a **per-release branch**, which is
exactly the kind of thing that stops existing when the release it names is over.

### The concrete defect

`v87` was retired for `v88` and never tagged. Note the second asymmetry, which is the
subtler half: the `GITHUB_BASE_REF` branch above probes `origin/<ref>` *and then* `<ref>`,
but the fallback resolves the bare name only — so it misses the `origin/v87` that still
survives. Two independent bugs stacked, either of which alone would have hidden the other.

Nothing in the `Makefile`, `scripts/`, or any workflow sets `QUALITY_BASELINE_BASE_REF`, so
a local `make quality` hits the fallback every time. It exits 2, and
`scripts/check_quality.sh:123` then deletes the previous report before any analyzer runs.
The failure mode is therefore *worse than no gate*: you lose the artifact that would have
told you the gate did not run.

This is also **72 of the 74 failures** in `scripts/test_quality_baseline_monotonicity.py`,
which the arch audit had previously written off as unexplained environment sensitivity.
That prior explanation is falsified and the falsification must be recorded.

### Implementation shape

Two things to fix, and do not fix only the first:

1. **Resolution** — the fallback must use the same `origin/<ref>` → `<ref>` probe the
   `GITHUB_BASE_REF` branch already implements. Factor the probe into one function and call
   it from both sites; two probe implementations is the same duplicated-authority shape the
   rest of the release is about.
2. **Identity** — the fallback must name something durable: a long-lived ref (`main`), or a
   ref derived from `VERSION`/`git tag`. Never the current or previous release branch.

Then make it self-reporting: an unresolvable fallback should be a **startup-validated
error whose message names the fix**, not a generic `MERGE_BASE_ERROR` at analysis time.

The ~101 `v87` literals in the test suite move to the same derived ref — that count is
itself evidence of how far one hardcoded string spread.

### Verification

```bash
env -u QUALITY_BASELINE_BASE_REF -u GITHUB_BASE_REF \
    poetry run python scripts/check_quality_baseline_monotonicity.py   # exit 0, real merge_base
pytest scripts/test_quality_baseline_monotonicity.py                   # 72 failures → 0
make quality                                                           # re-emits quality_report.json
```

Plus a regression test that runs the gate on a branch **not** named by the fallback — that
is the case the current code gets wrong.

---

## SA158 — Regenerate the stale `publish.yml` parity oracle

`Band A · Tier 2 · W2 · merge #4 · deps: none`

### The mental model

`scripts/test_gate_parity.py` proves the CI topology matches what the gate registry
declares. Some of those proofs are **literal oracles**: a hardcoded copy of the expected
content, compared against the real file. An oracle is a deliberate trade — you accept
maintenance cost in exchange for catching *any* drift, including drift a structural
assertion would wave through.

That trade only pays if the oracle is maintained.

### The concrete defect

`test_all_twenty_one_publish_run_values_are_structural` (`:1090`) compares `publish.yml`'s
ordered `run:` blocks against a literal oracle. Commit `d3d4c633` added two steps and
removed two `apt-get` lines and never touched the oracle.

The test is **red on HEAD**. Repository content versus repository content — no environment
dependence, no flakiness, no excuse.

### Why it is band A rather than a chore

A red test is not a failure signal; it is a **destroyed** failure signal. The next real
parity drift in `publish.yml` lands on an already-red test and is indistinguishable from
this one. And SA155 must register the gate suites **green** — a red test in the suite is a
direct blocker.

### The broader question this ticket must answer

The arch audit's change-cost probe named five more count-pinned literal oracles: `:1064`,
`:958`, and the four `all_five_conformance_gates` assertions at `:803`, `:809`, `:815`,
`:847`. Every one is the same bet. Decide per oracle:

- **Derive it** — read the real file and assert structure. Cheap to maintain, weaker.
- **Restate structurally** — assert the *properties* the oracle was protecting rather than
  exact text.
- **Re-carry it deliberately** — with a written rationale saying why exactness is worth the
  maintenance. This is a legitimate answer; silence is not.

### The review discipline

Regenerating an oracle is trivially easy and trivially wrong: `regenerate && commit` makes
the test green while proving nothing. The acceptance requires the diff be **reviewed line
by line**, each changed entry confirmed to correspond to an intended change in
`d3d4c633`/`d4b0e834`. If an entry does not, you have found a second, real defect.

---

## SA157 — Fix the SA117 scope-tool test that asserts the interpreter's exit code

`Band A · Tier 2 · W2 · merge #6 · deps: none · blocks SA124`

### The mental model

This is the purest example of a **false green** in the repository, and worth internalising
as a pattern rather than a one-off.

A test asserts an exit code. Two entirely different mechanisms produce that same code:

| Exit 2 from | Means |
|---|---|
| `argparse` | "the tool correctly rejected a bad argument" ← what the test intends |
| CPython | "can't open file: no such file" ← what actually happens |

The collision is **invisible** precisely because argparse chose 2 to match the shell
convention. The test is not weak; it is measuring nothing at all.

### The concrete defect

`scripts/test_check_sa117_scope.py:596-617`:

```python
subprocess.run(["python", "scripts/check_sa117_scope.py", ...], cwd=version_fixture["root"])
# asserts returncode == 2
```

The fixture root (`:85-96`) contains no `scripts/` subdirectory. The relative path never
resolves. The interpreter exits 2 before the tool is ever loaded.

The test passes today, would pass if `check_sa117_scope.py` were deleted, and would pass if
the tool **accepted the argument it is supposed to reject**.

Note this is not a house convention gone wrong: the same file uses `sys.executable`
correctly in three other places, including the sibling at `:619-631`. It is one
inconsistency in one file.

### Why this must precede SA124

Roadmap SA124 names this exact file as where its new acceptance criterion lands. Fix this
first, or SA124's divergence test gets written beside — and most plausibly copied from — a
guaranteed false-green, inside a suite nothing executes. Three defects compounding.

### Implementation shape

Copy the sibling at `:619-631` verbatim in shape:

```python
script = pathlib.Path(__file__).with_name("check_sa117_scope.py")
result = subprocess.run([sys.executable, str(script), ...], ...)
```

Then add the part that makes the test un-fool-able: **assert a distinguishing signal
alongside the exit code** — `"unrecognized arguments"` in stderr, or that the evidence file
was not written. An interpreter-level failure produces neither.

### Proof obligation

Delete or rename `check_sa117_scope.py`, confirm the test turns **red**, revert. That is
the demonstration that the test now measures the tool. Also
`grep 'subprocess.run(\["python"' scripts/test_*.py` must return zero hits — this class
should not be able to recur silently.

---

## SA159 — Route repo-source execution through the project interpreter

`Band A · Tier 2 · W1 · merge #5 · deps: SA137 (same file) · blocks SA155, SA134`

### The mental model

`python3` on `PATH` is **whatever the machine happens to have**. The project interpreter is
**the one the project declares**. Confusing them is fine right up until the repository uses
syntax the PATH interpreter cannot parse — and then the failure is a `SyntaxError` from a
file you did not think you were running, with no message naming the real cause.

`ruff.toml:8-11` states the invariant **verbatim**:

> *"Anything that executes repo sources must therefore use the project interpreter
> (`sys.executable` / the venv), never a bare `python` off PATH"*

So this is not a judgement call. The rule is written down and three sites violate it.

### The concrete defect

| Site | Code | Runs |
|---|---|---|
| `scripts/version_tool.sh:11`, used at `:28` | `PYTHON="${PYTHON:-python3}"` | the authoritative module-discovery shim |
| `scripts/lint_frontend.sh:57` | `python3 render_j2_template.py` | a repo source |
| `scripts/lint_frontend.sh:173` | `python3 render_j2_template.py` | a repo source |

All three work today. **By luck, not by contract**: both targets happen to parse under
3.12. The repository floor is 3.14, and ruff is configured to emit PEP 758 syntax that
nothing below 3.14 can parse.

The day `ruff format` collapses a two-type `except` in `module_discovery.py`,
`version_tool.sh check` dies with a `SyntaxError` from a shim. The version gate — the thing
that tells you your release is consistent — fails in a way that names neither the
interpreter nor the version.

`scripts/_python_requirement.sh` already exists and already probes candidate interpreters.
Neither script sources it. The solution is in the tree, unused.

### Implementation shape

Resolve the project interpreter (`poetry run python`, `$REPO_ROOT/.venv/bin/python`, or the
`_python_requirement.sh` probe) and **fail loudly with the required version** when none is
found. Taking whatever `python3` is on `PATH` as a fallback is the exact behaviour being
removed — do not reintroduce it as an "if all else fails" branch.

Then make the class self-policing: a pre-commit or CI rule rejecting `python3 <repo>.py` in
`scripts/*.sh` and `["python",` as an executor of a repo source in `scripts/test_*.py`.
That second pattern is SA157's defect, so the two tickets close each other's recurrence.

`scripts/check_ci_locally.sh:62-70` selects `python3` the same way but feeds it only a
stdlib heredoc — genuinely adjacent, not a violation. Bring it into the seam or document it
as deliberately excluded. Do not leave it unaddressed, because the next reader will
re-litigate it.

### Verification

Put a 3.12 interpreter first on `PATH`, then run `scripts/version_tool.sh check` and
`scripts/lint_frontend.sh`. Both must still succeed. That is the whole point.

### Why W1 rather than W2

`scripts/version_tool.sh` is SA137's file. Two worktrees editing it concurrently is a
merge conflict on a shell script that gates the release. SA137 merges first (#2), SA159
follows (#5) in the same worktree.

---

## SA155 — Give the gate layer a gate of its own

`Band A · Tier 1 · W2 · merge #7 · deps: SA156, SA157, SA158, SA159`

### The mental model

Every piece of first-party code in this repository has an **owning execution context** —
something that runs it and fails if it breaks. `TEST_DIRS` in `Makefile:150` names them.

`scripts/` is deliberately outside `TEST_DIRS` and outside `.coveragerc`. The reasoning is
sound: gate helpers are not product code and should not be dragged into the product
coverage metric.

But the consequence was not noticed: **gate code is the only first-party code with no
owning execution context** — while being the code every other gate's credibility rests on.

> The gates check the product. Nothing checks the gates.

### The concrete measurement

- 14 `scripts/test_*.py` suites. **4 wired to a target. 10 wired to nothing.**
- `git log -S` shows the orphans were **never** wired. This is not decay; the wiring never
  existed, and the population grows by one with every new gate.
- Executed under the project interpreter this pass: **959 passed, 74 failed**, across code
  nothing runs.

Those 74 are not mysterious. 72 are SA156. The other 2 are SA158 and SA157's false-green
sits in the same population. This is why SA155 sits behind all four.

### What is already closed — preserve it

Hosted **job membership** is genuinely closed by `sync_ci_gate_jobs.py:314-320`. Do not
disturb that; it is the working half.

The gap is the **suites** and the **non-`ci.yml` contexts**. And note precisely why parity
checking cannot find it: `check_gate_parity.py:2509-2511` **filters rather than asserts**.
So parity proves *registered → present*, and never *present → registered*. A suite that
exists but is registered nowhere is invisible to the very tool designed to catch that.

### The option choice, already made

- **Option 1 — take this.** One registered `check-gate-suites` target running
  `pytest scripts/ --no-cov`, keeping `scripts/` out of the coverage metric. Minimal, and
  it preserves the deliberate coverage decision.
- **Option 2 — leave to SA123.** A per-gate `self_test` registry binding. Finer-grained,
  but it bumps the registry schema, and SA123 is already doing registry work.
- **Option 3 — explicitly out of scope.** Relocating the helpers into a first-party
  package. It collides with SA124's in-flight `sa117_scope.json` edits.

### The criterion that carries the ticket

*"the gate is registered **green** — all 74 failures are resolved by the dependency tickets
before registration, verified by a recorded pass/fail baseline."*

Registering a red gate creates a **known-failing required check**, and a known-failing
required check gets bypassed within a week and then ignored forever. That outcome is
strictly worse than today, because today at least nobody believes the suites are covered.

Record the baseline before and after. It is the evidence.

### The loose ends to close while you are here

Six `UNOWNED_JOB_IDS` entries need each to be justified in writing or registered. One is
specifically named: `isolation-conformance` has **no Makefile target** and is invoked only
from `ci.yml:634` — meaning a developer cannot run it locally by any documented route.
Resolve that one explicitly rather than folding it into a blanket justification.

---

# Band B / W1 — Pins, interpreter, and dependency-spec authority

## SA137 — Add `quickscale_devtools` to version propagation

`Band B · Tier 1 · W1 · merge #2 · deps: none · blocks SA159, SA134`

### The mental model

QuickScale ships several Python packages out of one repository: `quickscale`, `quickscale_core`, `quickscale_cli`, `quickscale_devtools`, and twelve `quickscale_modules/*`. The repository holds **one** version number in the root `VERSION` file, and `scripts/version_tool.sh` is the machine that pushes that number into every place a version is written.

Think of `VERSION` as the single clock, and `version_tool.sh` as the mechanism that moves every hand on every dial. `check` asks "do all the dials agree with the clock?"; `update` sets them.

### The concrete defect

Look at the top of `scripts/version_tool.sh`:

```bash
PYPROJECTS=("$ROOT/quickscale_core/pyproject.toml" "$ROOT/quickscale_cli/pyproject.toml" "$ROOT/quickscale/pyproject.toml")
PACKAGES=("$ROOT/quickscale_core/src/quickscale_core" "$ROOT/quickscale_cli/src/quickscale_cli")
```

`quickscale_devtools` is in neither list. The modules *are* handled well — `_load_module_inventory()` shells out to the authoritative discovery shim (`quickscale_core/src/quickscale_core/contracts/module_discovery.py --list-modules`) and derives the twelve module paths, so adding a module needs no edit here. But the four top-level packages are a **hardcoded array**, and devtools was never added to it.

The drift is already real and observable today:

```
VERSION                                 → 0.87.0
quickscale_devtools/pyproject.toml:34   → version = "0.86.0"
```

Devtools is a release behind, and `make version-check` passes anyway, because it never looks.

### Why it matters (and why it is only Tier 1, not urgent)

Devtools is deliberately **maintainer-only**. Its own `pyproject.toml` header states it is intentionally absent from `PACKAGES` in `scripts/publish.sh` and `DEFAULT_PACKAGES` in `scripts/prepare_publish.py`. So a stale version does not ship to a user.

Hold this distinction clearly, because it is the most likely way to get this ticket wrong:

- **Version *parity*** — devtools should carry the repository version. **This is what SA137 fixes.**
- **Version *publication*** — devtools should be uploaded to PyPI. **This is explicitly NOT SA137.** Adding devtools to the publish package list would break the documented maintainer contract and require `PATH_DEPENDENCY_REWRITES` changes.

If a reviewer sees devtools appear in a publish list, the ticket has overreached.

### Implementation shape

The weak fix is to append devtools to the two arrays. The acceptance criterion "the propagation set is derived, not a second hand-maintained list" rejects that: it recreates the same class of bug for the *next* package. Prefer discovering top-level packages the way modules are already discovered — a directory scan for `quickscale*/pyproject.toml` at the repository root, or a single declared inventory that both `version_tool.sh` and the publish scripts read, with publication remaining a separate flag on each entry.

Note that `scripts/sa117_scope.json` **already lists** `quickscale_devtools/pyproject.toml` and `quickscale_devtools/src/quickscale_devtools/__init__.py` as `SA117 version pin surface` entries. The allowlist expected devtools to be in the lockstep set; the tool never caught up. That is your strongest evidence that this is a genuine omission and not a deliberate exclusion.

Also check whether devtools has a `__version__` in `src/quickscale_devtools/__init__.py` — a grep found none, so decide deliberately whether `update` should write one (matching the module pattern) or whether the `[project] version` alone is the pin surface. Whichever you choose, the scope file's phase-4 entry should match reality afterwards.

### Files

`scripts/version_tool.sh`, `quickscale_devtools/pyproject.toml`, `scripts/test_version_tool.py`, possibly `quickscale_devtools/src/quickscale_devtools/__init__.py`. Shared surface: `VERSION`, `Makefile`.

### Verification

`make version-check` (must now fail before the fix and pass after the devtools bump); `scripts/version_tool.sh update` followed by a clean `check`; new contract tests in `scripts/test_version_tool.py`. Note that `test_version_tool.py` copies the real script into a synthetic repository (`shutil.copy2` at line ~450) — your new discovery logic must work inside that hermetic fixture, so avoid depending on anything outside the copied tree.

---

## SA134 — Derive generated-project version assertions from authoritative pins

`Band B · Tier 2 · W1 · merge #8 · deps: SA137, SA159`

### The mental model

A generated QuickScale project pins runtimes: a Python version, a Django constraint, a PostgreSQL image tag, a Node image. Those pins have exactly one home:

`quickscale_core/src/quickscale_core/generator/runtime_pins.py`

```python
PYTHON_VERSION: str = "3.14"
PYTHON_CONSTRAINT: str = f">={PYTHON_VERSION},<3.15"
PYTHON_DOCKER_TAG: str = f"{PYTHON_VERSION}-slim-bookworm"
DJANGO_CONSTRAINT: str = ">=6.0.7,<6.1.0"
POSTGRES_VERSION: str = "18"
POSTGRES_DOCKER_TAG: str = f"{POSTGRES_VERSION}-alpine"
```

The module's own docstring states the intent: *"All templates that reference a pin use the same value from this module, so a single change here propagates to every emitted file."* Templates honour that — `docker-compose.yml.j2` line 3 emits `postgres:{{ postgres_docker_tag }}`.

**The tests do not.** They retype the literal.

### The concrete defect

Files carrying hardcoded `18-alpine`, `node:24`, or `python:3.14` include:

- `quickscale_core/tests/test_generator/test_templates.py`
- `quickscale_core/tests/generator/test_themes.py`
- `quickscale_cli/tests/test_beta_migration.py`
- `quickscale_cli/tests/utils/test_stale_compose_volumes.py`
- `quickscale_cli/tests/utils/test_railway_utils.py`
- `quickscale_core/tests/docker-compose.test.yml`

So `runtime_pins.py` is a single source of truth for *production* and a **second, shadow source of truth for tests**. Bumping PostgreSQL to 19 changes one production line and then breaks a scatter of tests that assert the old value — and the failure message says "expected 18-alpine, got 19-alpine", which reads like a regression rather than "you forgot to update the mirror".

### The subtlety that makes this Tier 2 rather than trivial

A test that reads `POSTGRES_DOCKER_TAG` and asserts the template emits `POSTGRES_DOCKER_TAG` is **tautological** — it will pass no matter what the value is, including nonsense. You are trading a brittle test for a vacuous one if you are careless.

The resolution is to be precise about what each assertion is *for*:

- **"The pin reaches the emitted file"** — derive from `runtime_pins`. This is a wiring assertion; tautology is fine because the point is that the plumbing connects, not what flows through it.
- **"We are not on a retired version"** — keep the literal. This is the *negative control* the acceptance criteria protect. A test asserting `"3.12" not in emitted_dockerfile` stays a literal deliberately, because its whole job is to name a specific bad value.

The acceptance wording — *"retired-version negative controls remain and still fail when a retired version is reintroduced"* — exists exactly to stop a blanket find-and-replace from deleting them.

### The proof obligation

*"bumping a pin requires no test edit, demonstrated by a temporary bump that leaves the suite green"*. Literally do this: change `POSTGRES_VERSION` to `"19"`, run the suite, confirm green, revert. Record it as evidence. If anything fails, a literal survived.

Note `quickscale_core/tests/docker-compose.test.yml` is a static YAML file, not Python — it cannot import `runtime_pins`. Decide whether it is in scope (it pins the *test harness* Postgres, arguably a different concern from the *generated project* Postgres) and say which, rather than leaving it ambiguous. This overlaps SA135, which owns the test harness's database; coordinating the answer with the W3 ticket is reasonable, but SA134 merges first (#8 vs #13), so state the decision and let SA135 honour it.

### Depends on SA137 because

Both tickets are about "the version fact has one home". SA137 establishes the derived-inventory pattern for repository package versions; SA134 applies the same discipline to runtime pins in tests. Sequencing them avoids two people inventing two different conventions for "read the authoritative value" in the same release.

---

## SA150 — Document and fail-hard the `QUICKSCALE_LOCAL_WHEELHOUSE` seam

`Band B · Tier 2 · W1 · merge #11 · deps: SA134 · blocks SA118`

### The mental model

When QuickScale generates a project, that project needs to depend on `quickscale-core`. Normally the generated `pyproject.toml` says something like `quickscale-core = "^0.87.0"` — resolved from PyPI.

But during development and acceptance testing, the version you want does not exist on PyPI yet. So there is an escape hatch: a **wheelhouse**, a directory of locally built `.whl` files. When one is in play, the generated project should depend on an exact local wheel *file* instead of a PyPI version range.

Two ways a wheelhouse is found (`_resolve_wheelhouse_dir()`, `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py:153`):

1. `QUICKSCALE_LOCAL_WHEELHOUSE` env var — an explicit, deliberate override used by installed-wheel acceptance runs.
2. A wheelhouse staged beside the running CLI install (`sys.prefix/<wheelhouse dirname>`) — implicit, for locally installed builds.

### The concrete defect

`_resolve_local_wheel_dependency()` at line ~175:

```python
wheelhouse = _resolve_wheelhouse_dir()
if wheelhouse is None:
    return None                      # (A) no wheelhouse at all — correct

normalized_name = dependency_name.replace("-", "_").lower()
candidates = sorted(wheelhouse.glob(f"{normalized_name}-*.whl"))
if not candidates:
    return None                      # (B) wheelhouse exists, no matching wheel
if len(candidates) != 1:
    raise DependencySyncError(...)   # (C) ambiguous — correctly fails hard
```

Returning `None` means "no local wheel applies, use the manifest version spec". That is right for **(A)** and wrong for **(B)**.

The two cases are semantically opposite:

- **(A)** You never asked for a wheelhouse. Falling back to PyPI is the correct, intended behaviour.
- **(B)** You explicitly set `QUICKSCALE_LOCAL_WHEELHOUSE` — you *stated* you want local wheels — and the wheel isn't there. Something is broken: a build step didn't run, a name normalization mismatched, the wrong directory was exported. Falling back to `^0.87.0` from PyPI silently produces a project that installs a **different artifact than the one under test**.

Note the asymmetry the code already contains: case **(C)**, two matching wheels, raises. Ambiguity fails hard; absence does not. That inconsistency is the tell.

The failure is quiet and delayed: the acceptance run proceeds, installs a published wheel, and reports success on the wrong artifact — or fails much later at install time with an unrelated-looking error.

### Why this is the second half of the ticket

`_resolve_wheelhouse_dir()` **already** fails hard on a malformed env var:

```python
if not wheelhouse.is_absolute() or not wheelhouse.is_dir():
    raise DependencySyncError(
        f"{_LOCAL_WHEELHOUSE_ENV} must name an absolute wheelhouse directory"
    )
```

So the seam has real, enforced contracts — absolute path, must exist, unambiguous wheels — that appear **nowhere in `docs/technical/`**. The only descriptions are code comments and the E2E test `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`. Someone hitting the error has to read the CLI source to learn the rules. That is the documentation half.

### Implementation shape

Distinguish (A) from (B). Give `_resolve_local_wheel_dependency()` enough information to know *why* there is no wheelhouse — either return a small result type from `_resolve_wheelhouse_dir()` carrying its provenance (explicit-env vs staged-beside-install vs none), or check the env var directly at the raise site. Raise `DependencySyncError` naming the env var, the directory searched, the glob pattern tried, and the wheels actually present — the last of these is what turns a five-minute debugging session into a five-second one.

The staged-beside-install wheelhouse (case 2) is a judgement call: it is implicit, not requested, so an unmatched wheel there is arguably closer to (A). State your choice explicitly in the doc rather than leaving it to be rediscovered.

### Guard rails

- *"a regression test asserts the raise (not a log)"* — a `caplog` assertion does not satisfy this. The call must raise.
- *"the unset-wheelhouse path is unchanged"* — the overwhelmingly common path is no wheelhouse at all. It must keep resolving from the manifest exactly as today. A regression here breaks ordinary project generation for every user.

### Audit bookkeeping

`docs/others/tech-audit.md` currently reports **zero open findings**. The wheelhouse seam is listed under **"Live watch items"**, not as a finding. So the closeout retires a watch item; it does not close a numbered finding, and the severity table stays at zero. (The roadmap's acceptance line has been corrected to match.) The header drift previously noted here — `Branch: v87` — was resolved by the 2026-08-21 regeneration and needs no action.

---

# Band B / W2 — Gates and declared wiring

Everything here merges **after** band A. SA124 in particular must not start before SA157
lands, because SA157 owns the file SA124's acceptance criterion writes into.

## SA124 — Unify SA117 scope-tool path authority

`Band B · Tier 1 · W2 · merge #10 · deps: SA155, SA157`

### The mental model

SA117 was a large, high-risk refactor around embedded-manifest and core version lockstep. To keep it controllable it was given a **scope guard**: an explicit allowlist of every file any SA117 phase may touch, in `scripts/sa117_scope.json` (~120 entries, each with a `path`, a `phase`, and `notes`). `scripts/check_sa117_scope.py` enforces it in several modes:

- `worktree` — do the changed files fall inside the allowlist?
- `emit` — print the allowlist, optionally filtered by phase
- `lock` — do candidate paths match the allowlist *exactly*?
- `lock-diff` — fail-closed proof that `poetry.lock` did not drift, normalising only the twelve approved module version leaves

Mental model: the allowlist is a **capability boundary**. The tool's job is to make it impossible to change a file nobody agreed to change.

### The concrete defect

A guard whose own contract is restated in several places can drift, and drift in a guard is worse than drift anywhere else — it fails *open*. The "required-path set" (which inputs each mode requires, and which paths it covers) is currently expressed independently in at least four places:

1. **The CLI** — `argparse` in `check_sa117_scope.py` (~line 826): `worktree.add_argument("--paths", nargs="*", default=None)` with a *runtime* check `raise ValueError("--paths is required for worktree mode")` at line 159. Note `--paths` is declared optional to argparse and required by hand later — that gap is itself a small instance of the problem.
2. **The Make target** — `Makefile:916-938` re-implements the same requirement in shell:
   ```make
   sa117-check:
   	@if [ -z "$(PATHS)" ]; then \
   		echo "Error: PATHS is required (space-separated list of changed files)."; \
   ```
   and again for `sa117-lock`, and again with different variables for `sa117-lock-diff` (`SA117_BASELINE_REF`, `SA117_EXPECTED_VERSION`).
3. **`--help` / the Make help text** — `Makefile:234-237` describes the requirements in prose: `"make sa117-lock-diff - Fail-closed poetry.lock drift proof (SA117_BASELINE_REF required)"`.
4. **`scripts/sa117_scope.json`** — the path data itself.

Four statements of one contract. Add a fifth consumer, or change a requirement in one place, and the others silently disagree.

Contrast this with how the same file handles the *module* inventory: `_authoritative_module_names()` (line ~48) shells out to the discovery shim and raises `LockDiffError` if it cannot. That is the pattern this ticket generalises — the file already knows how to do it right for one kind of fact.

### Implementation shape

Define the required-input/required-path contract once — most naturally as data in or beside `sa117_scope.json`, or as a declarative table in `check_sa117_scope.py` that argparse is built from. Then:

- argparse builds its `required=` flags and help strings from it, so `--help` cannot drift.
- The Make target stops re-checking emptiness in shell and lets the tool report the error, or reads the same declaration.
- A test enumerates the consumers and fails if one bypasses the source.

The last bullet is the durable part. *"a test fails if any consumer is added without going through that source"* means the enforcement must be structural, not a comment saying "keep these in sync".

### The advisory

`SA117E1-REV-004` is carried by this ticket. **Be aware before starting: that identifier appears nowhere in the repository except the roadmap line itself** — not in `CHANGELOG.md`, not in `docs/`, not in the scope JSON. Its original text is not recoverable from the tree. Your first action should be locating it (check the v87 review history in version control, or `docs/planning/sa117e-4-corrected-source-plan.md`). If it cannot be recovered, the acceptance criterion's *"or explicitly re-carried with rationale"* branch applies — record that the advisory text is lost and either close it as unrecoverable or restate what you believe it covered. Do not silently drop it.

### Why SA123 depends on this

Both tickets edit `scripts/gate_registry.json` and the `Makefile` gate surface. Doing SA124 first means SA123 registers its new gates against a tidied, single-authority path contract rather than against four drifting copies. Serialising them on one track keeps the registry off the cross-track conflict surface entirely.

---

## SA123 — Add dependency-vulnerability and security static-analysis gates

`Band B · Tier 2 · W2 · merge #12 · deps: SA124`

### The mental model

QuickScale's CI discipline is centralised in `scripts/gate_registry.json` — a declared list of every gating checkpoint, with each gate naming the **contexts** it must run in:

```json
"contexts": {
    "local-serial":  "scripts/check_ci_locally.sh serial mode",
    "local-parallel":"scripts/check_ci_locally.sh parallel mode",
    "hosted":        ".github/workflows/ci.yml hosted CI",
    "publish":       ".github/workflows/publish.yml release workflow",
    "e2e-trigger":   ".github/workflows/e2e.yml ordered path allowlist"
}
```

Each gate entry carries `id`, `description`, `required_contexts`, `bindings` (`make_target`, `ci_job`, `local_ci_stage`), `depends_on`, and `trigger_inputs`. `scripts/check_gate_parity.py` then proves that what the registry declares actually exists in every context — a gate cannot be green locally and absent in hosted CI.

**This is the key insight for the ticket: the registry is the gate's real home. A scanner wired only into `ci.yml` is not a QuickScale gate; it is a workflow step that parity checking will reject.**

### The concrete gap

`docs/others/tech-audit.md` names it precisely under **Tooling gaps**:

> **Dependency vulnerabilities:** no blocking `pip-audit`/Safety-equivalent scanner with a reviewed allowlist. Roadmap SA123 owns this for v88.
>
> **Security static analysis:** no focused Bandit/Semgrep-equivalent rules for subprocess shell use, unsafe deserialization, TLS disabling, Django raw/marked-safe sinks, and committed credentials. SA123 owns this for v88.

That second entry is effectively your rule list. Five named categories — treat them as the scope boundary. "Focused" is doing real work in that sentence: turning on Bandit's full default rule set across a repository this size produces a wall of findings, most of them noise in test code, and the predictable outcome is a blanket suppression that makes the gate decorative.

### Design tensions to resolve deliberately

**Blocking vs advisory.** A dependency-vulnerability scanner queries a database that changes without your code changing. A new CVE published overnight turns a green build red with no commit. That is *correct* — you want to know — but it means the gate can block an unrelated release. Decide and document how a fresh CVE is triaged under time pressure, because the reviewed-suppression mechanism is what stands between you and someone disabling the gate at 2am.

**Suppressions are the deliverable, not an afterthought.** *"every suppression carries a written rationale and an owner"*. A suppression file with entries but no rationale is worse than no gate — it looks like coverage. Model the format on the existing quality-waiver structure (`scripts/quality_waivers.json`) so the repository has one shape for "accepted exception".

**Registration is the acceptance criterion.** Both gates need `scripts/gate_registry.json` entries with correct `required_contexts` and `bindings`, and `scripts/check_gate_parity.py` must pass. Also consider `trigger_inputs`: a dependency scanner's trigger is `poetry.lock` and every `pyproject.toml`, not source files.

### The negative-control requirement

*"the gates fail on a deliberately introduced known-vulnerable pin and on a deliberately introduced flagged pattern, both reverted before merge"*. This is non-negotiable evidence. A scanner that runs, exits 0, and has never been shown to exit nonzero is unproven — misconfigured path filters are the single most common way security scanners silently scan nothing. Capture the failing output in the ticket evidence and revert both probes before merge.

### Files

`scripts/gate_registry.json`, `Makefile`, `.github/workflows/ci.yml`, `scripts/check_ci_locally.sh`, a new suppression/allowlist file, `pyproject.toml` (tool config + dev dependency). `scripts/sync_ci_gate_jobs.py` may need to know about the new jobs. Watch the `make quality` ceiling — the acceptance says leave it no worse than found.

---

## SA118 — Project every declared manifest default into wiring

`Band B · Tier 2 · W2 · merge #14 · deps: SA123, SA150`

### The mental model

Each module carries a `module.yml` manifest that **declares** its configuration surface. From `quickscale_modules/storage/module.yml`:

```yaml
config:
  mutable:
    backend:
      type: string
      default: "local"
      django_setting: QUICKSCALE_STORAGE_BACKEND
      validation:
        choices: ["local", "s3", "r2"]
    media_url:
      type: string
      default: "/media/"
      django_setting: MEDIA_URL
  immutable:
    private_media_enabled:
      type: boolean
      default: false
```

Every entry states four things: a type, a default, the Django setting it maps to, and (sometimes) validation. `mutable` options must have a `django_setting` — `quickscale_core/src/quickscale_core/manifest/loader.py:242` enforces it. `ModuleManifest.get_django_settings_mapping()` (`manifest/schema.py:225`) already exposes the name→setting map.

So the declaration is rich and validated. The question SA118 asks is: **does the generated project's wiring actually reflect every declared default, or do some defaults exist only inside imperative Python that re-states them?**

You have already seen a concrete example of the second pattern in SA150's file:

```python
backend = str((module_options or {}).get("backend", "local")).strip().lower()
```

That `"local"` is `storage.backend`'s manifest default, retyped in `module_dependency_sync.py`. Change the manifest and this code keeps the old default. Same class of bug as SA137 and SA134, one layer up.

### The scope boundary — this is the important part

There is a much larger, tempting project here: converting all imperative module wiring to a declarative manifest-driven pipeline. **SA118 explicitly is not that project.** The acceptance says: *"the imperative-to-declarative migration is not attempted — out-of-scope seams are ticketed, not converted."*

The line to hold:

- **In scope:** a default is *declared* in a manifest, and generated wiring does not carry it (or carries a stale copy). Fix the projection.
- **Out of scope:** a behaviour is imperative and has no manifest declaration at all. Do not invent a declaration for it. File a ticket.

The distinction is "is there already a declared fact being ignored?" — not "could this be declarative in principle?"

### Emission parity — expect this to be the bulk of the work

Changing what the generator emits collides with `quickscale_core/tests/fixtures/sa90_emission_manifests.json`. Read its `_provenance` block: it holds *exact path/hash/mode manifests* for three generator variants, deliberately built independently of the production emission mapping so it is a real check and not a mirror.

Its `baseline_evidence` entries show the established convention — each past rebaseline records ticket id, date, what changed, and which specific hashes moved:

> `"sa106": "Regenerated 2026-07-20 — three identity-bearing frontend source templates converted from .j2 to static verbatim-copy files (SA106). ... Deltas: useModules.ts.j2→static, ... 3 fixture hashes updated: useModules.ts, Dashboard.tsx, Sidebar.tsx."`

*"rebaseline emission parity with per-file rationale"* means adding an entry in exactly that register. A bulk regeneration with the note "updated hashes" destroys the fixture's value — the whole point is that a human certified each delta was intended.

### Dependencies

**SA123** — same track, sequencing only. **SA150** — real and cross-track: SA118 touches manifest version-spec handling, and it must sit on top of SA150's fail-hard seam rather than the current silent fallback. This is the single inter-track edge in the release; if the merge order slips, SA118 will build on behaviour that is about to change underneath it.

---

# Band B / W3 — Service-backed lifecycle

W3 holds the **exclusive PostgreSQL/Docker slot** for the release. Only one of these legs may be active at a time across all worktrees, and W3 takes scheduling priority while a leg is running — even though W2, not W3, is now the longest dependency chain. All three tickets ask the same question: *who owns the lifecycle of a thing we create?*

## SA151 — Recreate module migrations as clean initial schemas

`Band B · Tier 1 · W3 · merge #3 · deps: none · PostgreSQL slot`

### The mental model

Django migrations exist to move an **existing** database from schema A to schema B without losing data. That value proposition rests on one assumption: somebody out there is running schema A and needs to get to schema B.

QuickScale is pre-1.0 and explicitly not backward compatible across versions. The documented upgrade path is a **fresh database**. So the assumption does not hold — and migration history becomes pure cost: files to maintain, an ordering graph to keep consistent, and a slower apply.

### The current state

```
analytics:      0 migration files      ← no models, or models with no migration?
auth:           1
backups:        5      ← 0001_initial + 0002…0005
billing:        1
blog:           1
crm:            1
forms:          1
listings:       1
notifications:  1
orgs:           1
social:         1
storage:        0      ← same question as analytics
teams:          0      ← placeholder, not a shipped module
```

`backups` has accreted four incremental migrations (`remote_storage_context`, `restore_scope_and_versions`, `snapshot_substrate`, `restore_execution`) — visible feature history that will never be replayed by anyone, because nobody upgrades a QuickScale database in place. The other modules' `0001_initial` files are described as stale, meaning they no longer match current models even though they are numbered as initial.

`backups/0001_initial.py` is stamped `# Generated by Django 6.0.3 on 2026-03-26` — five months of model evolution sit between that file and today.

### Two things to determine before deleting anything

1. **`analytics`, `storage`, and `teams` have zero migrations.** `teams` is a known placeholder (`PLACEHOLDER_MODULE_NAMES` in `module_discovery.py` excludes it, and `AUTHORITATIVE_MODULE_COUNT = 12`). But `analytics` and `storage` are shipped modules — do they genuinely have no models, or are they missing migrations they should have? If it's the latter, that is a live defect this ticket should surface, and the acceptance phrase *"exactly one `0001_initial` per module with models"* is written to accommodate a legitimate zero.
2. **RLS and the `organization_id` policy.** Regenerating from models is only correct if the models carry everything the current schema has. If any row-level-security policy, index, or constraint lives in a `RunSQL` or `RunPython` step inside `backups` `0002`–`0005` rather than in the models, regeneration **silently drops it** and `makemigrations --check` will still report clean, because it only compares model state. Read all four before deleting them. This is the single highest-risk step in the ticket and the reason it holds the PostgreSQL slot.

### Verification is the real deliverable

- Exactly one `0001_initial` per module with models, nothing else.
- A generated project applies every module migration from an **empty** database in one pass.
- `makemigrations --check --dry-run` reports no pending changes for every module — this is what proves the regenerated files actually match the models.
- `make test-integration` passes.

Add a schema-level comparison if any `RunSQL` was found: dump the schema before and after and diff it. `--check` compares Django's model state, not the database, so it cannot detect a dropped raw-SQL policy.

### Policy record

The no-migration-history policy goes in `docs/technical/decisions.md`. Without it, the next contributor will "helpfully" add `0002_*` and reintroduce the problem. The decision should state the rule *and* the reason (pre-1.0, fresh-database upgrade path), so it can be revisited deliberately at 1.0 when the assumption changes.

---

## SA142 — Reuse and clean E2E Docker images

`Band B · Tier 1 · W3 · merge #9 · deps: SA151 · Docker slot`

### The mental model

Every Docker E2E run creates several kinds of object, and they have genuinely different natural lifetimes:

| Object | Should be | Why |
|---|---|---|
| **Image** | *stable and shared* | An expensive build artifact; identical inputs → identical image. Rebuilding it per run is waste. |
| **Container** | *per-run and disposable* | Carries run state; sharing one across parallel lanes causes interference. |
| **Port** | *per-run* | Two lanes on one port collide. |
| **Volume** | *per-run* | Carries database state that must not leak between runs. |

`scripts/test_e2e.sh` gets three of these four right, and rigorously so. Look at lines 483-500:

```bash
lane_container_prefix="$(sanitize_scope "${lane_prefix_base}-${BASHPID}")"
lane_compose_project="$(sanitize_scope "${lane_compose_base}-${BASHPID}")"
export QS_E2E_CONTAINER_PREFIX="$lane_container_prefix"
export COMPOSE_PROJECT_NAME="$lane_compose_project"
```

Per-lane, PID-scoped identity, with `cleanup_scoped_containers()` reclaiming by both the compose-project label and the name prefix, signal traps on TERM/INT/HUP, and a pre-cleanup pass before the run. This is careful code.

### The concrete defect

The image is the one that isn't handled — and the cause is a single missing line in `quickscale_core/src/quickscale_core/generator/templates/docker-compose.yml.j2`:

```yaml
  backend:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        INSTALL_DEV: "true"
    container_name: {{ project_name }}_backend
```

There is a `build:` stanza but **no `image:` key**. When Compose builds a service with no explicit image name, it derives one from the project name: `<compose_project>-backend`.

And `COMPOSE_PROJECT_NAME` is exported as `${lane_compose_base}-${BASHPID}` — deliberately different every run.

So image identity inherits container identity. Consequences:

1. **No reuse.** Every run builds from scratch under a new name, even with byte-identical inputs. That is the "measurably faster second run" the acceptance asks for.
2. **No reclamation.** Cleanup is `docker compose down -v --remove-orphans` plus container removal by label and name. `down` removes containers, networks, and volumes — **not images**. Nothing in the script ever runs `docker image rm` or `docker image prune`. Every run permanently leaks one image.

Confirm the leak before starting: `docker images | grep backend | wc -l` on this machine, given the E2E history, is your baseline evidence.

### Implementation shape

Give the backend service an explicit `image:` whose tag derives from **build inputs**, not from run identity — the Dockerfile, the Python constraint, the lockfile, the installed module set. Content-addressing (a hash of those inputs) gives correct reuse *and* correct invalidation: change an input, get a new tag automatically; change nothing, hit the cache.

Then add image reclamation to the cleanup path for the variable images that remain, filtered by a QuickScale-owned label so you never remove an unrelated user image. **A blanket `docker image prune -a` is unacceptable** — E2E runs on developer machines.

`--no-cleanup` must still preserve everything needed for diagnosis. Its current output tells the user exactly how to clean up by hand (lines 513-516); extend that guidance to images rather than leaving a new class of leftover undocumented.

### Watch out

This edits a **generated-project template**, so it changes emitted output — the SA90 emission-parity fixture will need the same rebaseline-with-rationale treatment described under SA118. Two tickets touching that fixture in one release, on different tracks; the sync-before-merge-back procedure must preserve both entries.

### Depends on SA151 because

Sequencing on the exclusive service slot, not a code dependency. SA151 should hold the PostgreSQL slot first because its migration regeneration is the riskier, more schedule-sensitive leg.

---

## SA135 — Give test suites an owned PostgreSQL lifecycle

`Band B · Tier 2 · W3 · merge #13 · deps: SA142 · PostgreSQL + Docker slot · **carries SA163**`

### The mental model

Compare the two database-backed gates as they exist today:

**The E2E gate owns its database.** `scripts/test_e2e.sh:535`: *"pytest-docker will automatically start PostgreSQL"*, backed by `quickscale_core/tests/docker-compose.test.yml`:

```yaml
services:
  postgres:
    image: postgres:18-alpine
    ports:
      - "5432"   # Dynamic port — Docker assigns an available host port
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
```

Started on demand, health-checked, dynamically ported, torn down after.

**The integration gate borrows one.** `scripts/test_integration.sh`, header:

```
# Requires PostgreSQL 18 running on localhost:5432.
#
# Prerequisites:
#   - PostgreSQL 18 running on localhost:5432
#   - All test databases pre-created (see ci.yml create-test-databases step)
#   - A LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER role ... with
#     ownership + schema grants on all module test databases
```

Three preconditions that **somebody else** must have satisfied, out of band. On hosted CI a workflow step does it. On a developer machine, a human did it once, months ago, and may not remember how.

SA135 is: make the integration gate own its server the way the E2E gate already does. The pattern is proven and in-tree — this is largely propagation, not invention.

### Why the fix is delicate

The role contract is not incidental. `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` — specifically `NOBYPASSRLS` — is what makes row-level-security tests **meaningful**. A superuser bypasses RLS entirely, so isolation tests running as one would pass without proving anything. `scripts/provision_test_roles.sh` and `scripts/test_isolation_conformance.sh` exist to enforce this.

A hasty containerised swap that connects as the default `postgres` superuser would leave every integration test green and every multi-tenant isolation guarantee unverified. That is the worst possible outcome for this repository, given the locked child-table RLS policy. **Preserving the role contract is the acceptance criterion that matters most.**

### The negative control

*"the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping"*.

The tempting shape for provisioning code is:

```python
if not postgres_available():
    pytest.skip("PostgreSQL not available")
```

That converts an infrastructure failure into a green build with silently zero integration coverage — the same silent-fallback family as SA150, one layer up. If provisioning fails, the gate must fail. There is an existing asserted-unavailability control; it must survive the rewrite.

### Proof

*"`make test-integration` passes on a machine with no PostgreSQL running"*. Test it honestly — stop any host PostgreSQL, confirm nothing is listening on 5432, run the gate. If it passes because it quietly found a server you forgot about, you have proven nothing.

### Documentation

`docs/technical/validation_policy.md` currently encodes the out-of-band assumption:

> Integration | `make test-integration` | ... | PostgreSQL 18 per-module test DB | `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER`

and the Testing Standards section describes the precondition in prose. Both need updating — this ticket changes a documented contract, which is why `validation_policy.md` is on its conflict surface.

### Depends on SA142 because

SA135 will provision a containerised PostgreSQL, so it should adopt whatever image-identity convention SA142 establishes rather than seeding a second, competing one. This is a genuine ordering dependency, not just slot scheduling.

---

## SA163 — Derive the CI PostgreSQL environment from one authoritative source

`Band B · Tier 2 · W3 · merge #13 — **executes inside SA135**, not as a separate pass`

### The mental model

The gate registry answers *which* gates run in *which* contexts. It does **not** answer
*what environment those gates require*. That second question is answered nowhere
declaratively — it is hand-replicated as shell.

### The census

Fourteen stations state the same environment:

| Thing | Copies | Where |
|---|---|---|
| PGDG PG18 install | 4 | `ci.yml:92-107`, `ci.yml:408-427`, `publish.yml:161-187`, `e2e.yml:74-91` |
| PG18 verification | 4, **divergent** | three check `command -v` *and* `--version \| grep "(PostgreSQL) 18"`; `e2e.yml:92` checks only `test -x` |
| `createdb` lists | 4 | across the same workflows |
| grant loops | 4 | ditto |
| `QS_*_DB_USER` blocks | 5 | ditto |
| the whole thing **as a Python literal** | 1 | `scripts/test_gate_parity.py:1125-1180` transcribes the shell verbatim |

That fourteenth station is the tell: a parity test that *transcribes* what it checks is not
an independent oracle — it is a fifteenth copy wearing a test's clothes.

### The live question this ticket must settle

`nightly-bypassrls.yml:81-82` installs plain `postgresql-client` — Ubuntu 16.x, **no
PGDG** — while creating `test_quickscale_backups` and setting `QS_BACKUPS_DB_USER`. That
runs against `ci.yml:93-95`'s own statement that the backups DR engine enforces a
PostgreSQL 18 `pg_dump`/`pg_restore` contract which 16.x fails.

Determine whether `make test-bypassrls` actually reaches a `pg_dump`/`pg_restore` path. If
it does, this is a **live defect**, not a cosmetic divergence, and it gets fixed here.

### Two divergences that are correct — do not "fix" them

Both were verified this audit pass. Refactoring blindly will break them:

1. The 6-entry `QS_*_DB_USER` block at `ci.yml:627-632` is **exactly** `orgs` plus
   `RLS_MODULES` from `test_isolation_conformance.sh:141`. It is derived, not truncated.
2. The isolation job's 11-database list **omits `backups`** because that job runs no
   backups tests.

Document both as deliberate in the refactor, or the next reader will "unify" them away.

### The option choice, already made

**Option 1**: one `scripts/provision_ci_postgres.sh`, four callers, module list derived
from the discovery shim exactly as `check_sa117_scope.py:48` already does. Option 2 (an
`environment` block in the gate registry) only if SA123's registry work lands cleanly
first, since both bump the registry schema.

### Why inside SA135

SA135's allowlist already spans `scripts/test_integration.sh`,
`scripts/provision_test_roles.sh`, the `Makefile`, and the documented DB precondition.
SA163 is a second pass over the same files with the same exclusive slot. Two tickets, one
change. It inherits SA135's PostgreSQL + Docker slot.

### Non-negotiable invariants across the refactor

`QUICKSCALE_ALLOW_BYPASSRLS: "0"` at `ci.yml:626` and the restricted-role isolation
connection must survive **unchanged**. These are the same RLS-meaningfulness guarantees
SA135's role contract protects; losing them here loses them everywhere.

---

# Band C — Bounded independent fixes

None of these blocks anything. Each has a small, well-understood blast radius. They exist
as **slack filler**: when a worktree finishes a band-B leg and its next leg is waiting on
another worktree, it takes one of these rather than idling or — much worse — widening the
ticket it just finished.

**Band C may slip past the release. None may displace a band-A or band-B leg.**

## SA160 — Share one correct CSRF-token helper in the React theme

`Band C · Tier 2 · W3 · merge #17`

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

`Band C · Tier 3 · W3 · merge #16`

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
rebaseline with per-file rationale — the same treatment described under SA118. Sequenced
after SA135 on W3 so the fixture edits stay serialized within the worktree.

---

## SA160 / SA161 sequencing note

Both are W3 and both touch `quickscale_core/tests/fixtures/sa90_emission_manifests.json`,
as do SA142 (merge #9) and SA118 (merge #14, W2). SA118 is the one that crosses worktrees.
Each rebaseline **appends** its own `baseline_evidence` entry; none may replace a prior
one. The sync-before-merge-back procedure has to preserve every entry.

---

## SA162 — Fix the deprecated bool inversion in the CSRF AST gate

`Band C · Tier 3 · W1 · merge #15`

### The concrete defect

`scripts/check_csrf_exempt_gate.py:271` uses `~val != 0` where `val` may be a `bool`. That
raises `DeprecationWarning` on 3.12+ and is **removed in Python 3.16** — verified under
`-W error::DeprecationWarning` on 3.14.6.

Reachable only when analysed source contains a literal `~True`/`~False`, so the cost is
future breakage, not present miscomputation. Hence Tier 3.

### The correction to carry — read this before touching the line

The arch audit's suggested fix is **`not val`, and it is wrong. Do not apply it.**

The function evaluates the truthiness of a *bitwise invert in analysed source*:

| Expression | Value | Truthy? |
|---|---|---|
| `~True` | `-2` | **yes** |
| `not True` | `False` | **no** |

Substituting `not val` would make the CSRF gate **misjudge every `~<constant>` operand it
sees** — turning a dormant deprecation into a live correctness bug in a security gate.

The correct fix is `~int(val) != 0`, which preserves the semantics exactly.

This is worth noting as a pattern: an audit's *finding* and an audit's *suggested fix* carry
different levels of verification. The finding here was correct; the fix was not.

### Acceptance shape

Pin the semantics with a test asserting the gate's verdict on analysed source containing
both `~True` and `~False`, so nobody can make this substitution later. Run the gate under
`-W error::DeprecationWarning`. Record the correction in the arch audit when retiring the
red flag — the wrong fix should not outlive the finding.

---

## SA165 — Discharge the tech-audit watch items that carry an action

`Band C · Tier 3 · W1 · merge #18`

### The mental model

The tech audit's *Notes* hold thirteen items. Most are **accepted trade-offs** or are owned
elsewhere — `SA150` owns the local-wheelhouse seam, `SA137` owns the devtools version
drift, and integration-branch CI, generator lock generation, the DB-free healthcheck, the
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
`tech-audit.md` is the declared SSOT for that class. Same family as SA150, one layer over.

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

`Band C · Tier 3 · W1 · merge #19 · deps: SA151`

### The mental model

A watch item is a bet: *"this is not a problem yet, and here is the trigger that would make
it one."* A watch item whose trigger **cannot be evaluated** has stopped being a bet and
become debt — it costs a read every audit pass and can never fire.

Five items are carried. Three are simply not fired and need no work. Two carry explicit
actions, and one is a naming question that becomes load-bearing on a specific trigger.

### 1. The SA92 migration-squash tuple — the trigger cannot be evaluated

An exhaustive search for `squash` returns only `git subtree --squash` in
`git_utils.py:302-345`, which is unrelated. The string `SA92` appears **nowhere in the
tree** except the audit's own prior line.

The audit's instruction is explicit: **re-anchor against SA151** — which deletes and
regenerates every module migration, making it the natural anchor — **or retire it. Do not
carry it a third pass unevaluated.**

This is the same lost-identifier pattern SA124 records for advisory `SA117E1-REV-004`. Two
instances in one release is a pattern worth naming: an identifier referenced only by the
document that carries it has no home.

### 2. Privileged-command pair — values agree, claimed authority does not

`production.py.j2:185` and
`quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:36` both hold
`frozenset({"migrate", "createcachetable"})`. The values are **verified equal**.

But the `apps.py` docstring calls itself *"the single source of truth for which commands are
privileged"* while the template holds an independent copy. The defect is the **claim**, not
the value.

Make the claim true — either the template reads the runtime frozenset, or the docstring
stops claiming sole authority — **with a test asserting the two cannot diverge.** A
governance artifact that says "single source of truth" beside a second copy is worse than
silence, because it stops the next reader from checking.

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

Module universe in environment lists, frontend runtime module keys, and the now-absorbed
watch half of Finding 13. Keep their triggers intact — restating is the work, not removing.

---

## SA166 — Require a testimony trail for behavioural commits

`Band C · Tier 3 · W2 · merge #20 · deps: SA155, SA118`

### The mental model

Every other ticket in this release makes a *machine* tell the truth. This one makes a
*commit* tell the truth.

### The evidence

`d3d4c633` and `d4b0e834` were both titled **"v0.87.0: QuickScale 0.87.0"** while in fact
changing hosted and publish provisioning. `d3d4c633` also left a repository conformance test
red — that is TA66, which is SA158, which is merge #4 of this release.

Both audits independently flagged the same shape: **a release-shaped message carrying a CI
topology change**. It was read closely only because the arch audit's delta-classification
step treats unlabeled-behavioural commits as read-at-full-depth. Absent that convention, it
would have shipped unexamined — and it did ship a red test.

### Why it is Tier 3 and sits behind SA155

The audit records this as **maintainer-process risk**, not a source finding. And a process
gate is worth very little while the gate layer it would run in is itself unexecuted — which
is exactly the SA155 problem. Fix the layer, then add to it.

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

# Post-v88 — recorded, not scheduled

These three are in the roadmap so the findings are not lost. **Listing a sub-item here does
not authorize implementing it**, and none may be pulled into a v88 ticket.

## SA152 — Refresh the beta-migration maintainer targets

`Post-v88 · Tier 3 · deps: SA151`

The 2026-08-21 audit found the **mechanics current**: the Makefile flag surface (`DONOR`,
`RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()`, every
command in `VERIFICATION_COMMAND_SPECS` still exists, and the file-ownership taxonomy is in
sync and enforced by 7 passing conformance tests. So this is not a rot ticket. Four residual
gaps:

- **The SA151 collision — the reason this is deps-blocked.** The workflow's verification
  stack runs `quickscale manage migrate` against a recipient that may carry an existing
  database. SA151 makes a **fresh database the only upgrade path**, invalidating the
  in-place workflow's implicit assumption. Resolve *after* SA151 merges, not before.
- **No end-to-end exercise.** The targets appear in no CI workflow and no
  `scripts/gate_registry.json` entry. Coverage is unit-level taxonomy conformance only, so
  breakage surfaces first for a maintainer **mid-migration** — the worst possible moment.
- **Silent skip in the conformance gate.** `_template_emitted_paths()` calls
  `pytest.skip()` when the template tree is not found, so a path-resolution regression turns
  the ownership gate **green instead of red**. Same silent-fallback family as SA150 and
  SA165.
- **Stale doc provenance.** `beta-site-migration.md` is headed *"shipped in v0.81.0"*
  against `VERSION` 0.87.0, and describes the tool as *"backed by Python scripts under
  `scripts/`"* when `scripts/beta_migrate.py` is an eight-line wrapper over
  `quickscale_devtools`.

## SA153 — Close the property-portal basics gap in `listings`

`Post-v88 · Tier 2 · deps: none`

**The highest-value post-release work**, driven by the planned `buenosairesproperties.com`
migration. The framing that matters: the gap is **not module existence**. `listings` ships a
deliberately generic `AbstractListing` plus a concrete `Listing`, and `blog` is
substantially complete. The gap is **property-vertical depth and public presentation**, and
every sub-item is a *basic* — a real-estate portal cannot launch without it.

The structural problem underneath most of the sub-items: the documented extension answer is
**subclassing `AbstractListing`**, but `views.py`, `urls.py`, `admin.py`, and `ListingFilter`
are all bound to the **concrete** `Listing`. So subclassing today yields a model and an admin
base but **no working public views, URLs, or filters** — the Tier 2 abstract-model contract
in [module-extension.md](module-extension.md) is half-delivered. Fixing that unlocks
attributes, filtering, and most of the rest at once.

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

`Post-v88 · Tier 3 · deps: SA153`

An **inventory, not schedulable work**. Deliberately held behind SA153 so the basics land
first and none of these widens that ticket. Map/geocoding, saved searches and match alerts,
agent/office profiles, portal syndication feeds, virtual tours, featured placement tied to
the `billing` credits ledger, blog↔listing cross-linking, and PostgreSQL `SearchVector`
full-text search.

Discharged only when every sub-item has been promoted to its own ticket with its own
acceptance criteria, or explicitly dropped with a written rationale.

---

## Reading order

### If you are executing

Follow the merge order in the roadmap. It is the answer.

### If you are coming to this cold and want the model

Each step builds the one after it:

1. **SA157** — the purest false green. Two mechanisms, one exit code. Ten lines. Once you
   see it, you see the whole band-A argument.
2. **SA156** — the same shape at repository scale: one stale string, 72 test failures, and
   an execution rule nobody could have satisfied.
3. **SA155** — the structural version. Not "a test is wrong" but "an entire category of code
   has no owner."
4. **SA137** — the smallest, clearest instance of duplicated authority; the release's other
   half in one file.
5. **SA150** — the clearest instance of silent fallback; four lines of code, precisely
   diagnosable.
6. **SA134** — duplicated authority plus the tautology trap, which is where judgement starts
   mattering.
7. **SA142** — lifecycle ownership, with a single missing YAML key as the root cause.
8. **SA151, SA135** — the two service-lifecycle tickets, both carrying real correctness risk
   (dropped RLS policies; bypassed RLS roles).
9. **SA124, SA123, SA118** — the tooling and wiring tickets, which need the most context
   about existing conventions (scope allowlist, gate registry, emission-parity fixture).
10. **SA163** — duplicated authority at its widest: fourteen stations, one environment.

### The three traps this release keeps setting

Worth holding as a set, because each appears in more than one ticket:

- **The tautology trap** (SA134). A test that reads the authoritative value and asserts the
  authoritative value passes for any value, including nonsense. Derive *wiring* assertions;
  keep *negative controls* literal.
- **The wrong-fix trap** (SA162, and SA155's Option 3). An audit's finding and an audit's
  suggested fix carry different verification. `not val` would have broken the CSRF gate.
- **The green-by-absence trap** (SA157, SA155, SA135, SA152, SA165). Skipping, filtering,
  and unresolvable paths all produce green. Every one of them must be made to produce red.
