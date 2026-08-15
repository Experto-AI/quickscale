# SA117e-4 — Corrected-Source Resumption, Seal, and Verification Plan

> **Execution identity:** `/home/victor/code/quickscale-wt-track3` at corrected-source
> `HEAD=8fe7cdb1374de831746c34ed0a898d406cdcba1c`, with repository `VERSION=0.87.0`.
> **Lifecycle:** this plan governs SA117e-4 resumption steps 1–5 only. The core tag remains
> local and unpushed. Core-tag push and every PyPI action remain with SA96-PUBLISH.
> **Document boundary:** `docs/planning/sa117e-4-release-plan.md` is historical evidence and
> must remain byte-unchanged. This file is standalone: every mechanism needed to execute or
> review the ceremony appears below, inline.

## Objective, scope, and fixed facts

Resume SA117e-4 from corrected source, prove the already-published twelve split branches
are tree-identical to that source, preserve and rebind the local annotated `0.87.0` tag,
obtain a clean installed all-module branch proof, freeze and obtain human confirmation of
the twelve-row pre-seal state, seal and verify all twelve namespaced split tags, prove a
clean default installed apply with exact prompt/response-consumption evidence, and only then
retain and verify a local restoration anchor before requesting a separate confirmation to
delete the stale teams split branch.

In scope:

- local source/worktree identity and validation;
- temporary worktrees, installed-wheel fixtures, and retained evidence under one unique
  `/tmp/quickscale-sa117e4-corrected-evidence-*` directory;
- the local `refs/tags/0.87.0` rebind, its explicit local backup ref, the durable local
  `refs/sa117e4-backup/teams-branch/0.87.0` restoration anchor, twelve namespaced remote
  split-tag pushes, and the separately confirmed teams-branch deletion;
- runtime reads of remote state immediately before each gate or mutation.

Out of scope:

- repository file edits of any kind during SA117e-4 execution;
- edits to the historical plan, roadmap, decisions, or changelog;
- republishing a mismatched split branch without a new independently reviewed plan;
- pushing the core tag, a broad tag push, release creation, or any PyPI action.

Two standing facts bind every phase:

1. `make quality` is expected to exit `2` only for the accepted SA140
   `_execute_apply_steps_locked` complexity result (CC 56 against 55), with monotonicity
   passing and no waiver. That result binds only SA96-PUBLISH's later green gate; it does
   not block SA117e-4.
2. `refs/heads/splits/teams-module` is a thirteenth, non-authoritative branch. It is never
   included in the twelve-module seal or pre-seal table. It may be deleted only after all
   step-5 checks pass, after its freshly read exact SHA is fetched and retained under the
   named local backup ref, and under a separate maintainer confirmation bound to that SHA
   and used in that same exact-SHA lease.

## Absolute prohibitions

- Never run `git push --tags`.
- Never push `refs/tags/0.87.0`; the core tag stays local and unpushed throughout this child.
- Push only the twelve explicit namespaced `refs/tags/splits/<module>-module/0.87.0` refs
  through the reviewed seal machinery. Their `splits/` prefix cannot match the publication
  workflow's `[0-9]*` or `v[0-9]*` tag globs.
- Perform no PyPI, TestPyPI, GitHub Release, or core publication action.
- Pass neither `EXPECTED_REMOTE_SHA` nor `ABSENT` to a seal command. Also omit
  `PREVIOUS_VERSION` for `0.87.0`.
- Never move, force-update, or delete a remote split tag after it has been pushed. A partial
  seal is diagnosed and rerun; an existing tag is acceptable only at its intended commit.
- Never treat this plan, its independent review, or an earlier confirmation as either of
  the two execution-time maintainer confirmations.

## Evidence ledger and authority

`snapshot_id=SA147-CORRECTED-PLAN-DISCOVERY-2026-08-15`,
`snapshot_reused=true`. This plan relies on that snapshot for the unchanged SA147 topology
and invoked-behavior findings; no replacement discovery is required before execution.

| ID | Authority and binding | Fact used |
|---|---|---|
| E-01 | Discovery snapshot `SA147-CORRECTED-PLAN-DISCOVERY-2026-08-15`, reused for this exact goal/scope | `git subtree --rejoin` advances worktree HEAD; exact-ref force-with-lease is ref-bound; seal-all freezes the twelve-module inventory, serially pushes one explicit namespaced tag, verifies tag and branch, stops on failure, and never moves a pushed tag; installed apply answering no at the destructive gate exits 1 after steps 1–10; a restoration push requires the local repository to possess and retain the object named by its source ref. |
| E-02 | `docs/technical/roadmap.md:209-218`, read from corrected source | Owns the five resumption steps and the two standing facts. |
| E-03 | `docs/technical/decisions.md:1153-1206`, read from corrected source | Owns the six-step lockstep order, mutable-loop/immutable-seal boundary, no-override seal contract, explicit tag refspec, and accepted client-side race residual. |
| E-04 | `Makefile:1202-1240`, `scripts/publish_module.sh:1-27`, and `scripts/publish_module.py:555-823,1252-1416` | `publish-module` alone uses exact branch expectations; `seal-modules` passes `--seal-all`; seal-all freezes inventory, runs serially, accepts no expected-SHA input, and performs final status verification. |
| E-05 | `quickscale_core/src/quickscale_core/utils/git_utils.py:855-897,900-973` | `--rejoin` is part of publication split behavior and exact-SHA branch pushes use a ref-qualified force-with-lease. No branch publish is authorized by this plan. |
| E-06 | `quickscale_core/src/quickscale_core/contracts/module_discovery.py:48-53,165-223,481-497` | Manifest discovery is the inventory source; placeholders including teams are excluded; count drift away from twelve fails hard. |
| E-07 | `.github/workflows/publish.yml:1-12` | Only pushed tags matching `[0-9]*` or `v[0-9]*` trigger the PyPI workflow; namespaced split tags do not match. |
| E-08 | `scripts/provision_installed_venv.sh:1-18,20-51` | Provisioning expects absolute source/output paths, exits 0 with `venv/` and `work/`, exits 2 for bad invocation, and otherwise fails nonzero. |
| E-09 | `quickscale_cli/src/quickscale_cli/commands/plan_command.py:966-982,1083-1123,1203-1231`, `plan_selection.py:59-82,147-173` | The retained plan stdin has exactly seven corrected-source prompts: package, theme, modules, three Docker choices, and save. |
| E-10 | `quickscale_cli/src/quickscale_cli/commands/apply_support.py:85-102` and `apply_command.py:3671-3706` | For the selected Docker config, apply has exactly three prompts: Docker-output, proceed, and late destructive/remote confirmation; accepting all required gates permits a clean exit. |
| E-11 | `scripts/verify_public_module_apply.py:145-251,286-311,388-430,595-705` plus the reused snapshot's `invoked behavior` entry | The approved harness preserves argv/stdin/cwd, owns exact Compose cleanup, emits JSON evidence, and returns 0 only for successful apply verification. It captures child output internally but does not expose successful-child prompt transcript or stdin-consumption evidence, so Phase 5 preserves harness acceptance and adds a separate isolated proof. |
| E-12 | `docs/planning/sa117e-4-release-plan.md` | Historical transcription source only. It remains unchanged and carries no mechanism by reference into this plan. |

Repeated-read evidence ledger: none; no file or seam was revisited after its initial
snapshot-backed or top-anchored inspection.

## Common execution contract

Run all blocks in Bash from the corrected-source workspace. Start a new operator shell at
phase 1. Keep that shell through the phase-4 stop when practical. If it is lost, rerun the
phase-1 identity/setup block, set `qs_evidence` to the retained evidence directory, and
source its `session.env`; do not infer dynamic values from memory.

Every unannotated command is expected to exit `0`. `set -euo pipefail` makes any other exit
an immediate stop. Never continue after an assertion, remote query, comparison, prompt-count
check, harness, or cleanup failure.

## Phase 1 — Resume against the corrected source

**PHASE GOAL:** Bind this execution to the required workspace, commit, version, clean
executable state, authoritative module inventory, and known validation baseline.

**SCOPE_IN:** Read repository state; create only the evidence directory and ignored quality
reports. No Git ref or remote mutation.

**LIKELY FILES/SYMBOLS:** Read-only: `VERSION`, `Makefile`, `scripts/`, `quickscale/`,
`quickscale_cli/`, `quickscale_core/`, `quickscale_modules/`, and
`authoritative_module_names`. The only permitted worktree delta is this new planning file.

**EXECUTION MODE:** serial.

**DEPENDS ON:** Independent plan review of this complete file returned `STATUS: ok` and the
orchestrator explicitly authorized SA117e-4 execution. Review alone is not authorization.

**COMMANDS AND EXPECTED RESULTS:**

```bash
set -euo pipefail

qs_repo=/home/victor/code/quickscale-wt-track3
qs_source=8fe7cdb1374de831746c34ed0a898d406cdcba1c
qs_version=0.87.0
qs_origin=https://github.com/Experto-AI/quickscale.git
qs_venv="$qs_repo/.venv"
qs_python="$qs_venv/bin/python"
qs_plan=docs/planning/sa117e-4-corrected-source-plan.md
qs_backup_ref=refs/sa117e4-backup/core-tag/0.87.0
qs_evidence=$(mktemp -d /tmp/quickscale-sa117e4-corrected-evidence-XXXXXX)
printf '%s\n' "$qs_evidence" | tee "$qs_evidence/EVIDENCE_ROOT"

test -d "$qs_repo/.git" || test -f "$qs_repo/.git"
test "$(git -C "$qs_repo" rev-parse HEAD)" = "$qs_source"
test "$(git -C "$qs_repo" show "$qs_source:VERSION")" = "$qs_version"
test -x "$qs_python"
git -C "$qs_repo" remote get-url origin | tee "$qs_evidence/origin.txt"
test "$(cat "$qs_evidence/origin.txt")" = "$qs_origin"

git -C "$qs_repo" status --porcelain --untracked-files=all \
  | tee "$qs_evidence/source-status.txt"
while IFS= read -r status_line; do
  test "${status_line:3}" = "$qs_plan"
done < "$qs_evidence/source-status.txt"

git -C "$qs_repo" diff --quiet "$qs_source" -- \
  Makefile scripts quickscale quickscale_cli quickscale_core quickscale_modules VERSION
test -z "$(git -C "$qs_repo" status --porcelain --untracked-files=all -- \
  Makefile scripts quickscale quickscale_cli quickscale_core quickscale_modules VERSION)"

mapfile -t qs_modules < <(
  "$qs_python" \
    "$qs_repo/quickscale_core/src/quickscale_core/contracts/module_discovery.py" \
    --list-modules
)
test "${#qs_modules[@]}" -eq 12
printf '%s\n' "${qs_modules[@]}" | tee "$qs_evidence/authoritative-modules.txt"
test "$(sort -u "$qs_evidence/authoritative-modules.txt" | wc -l)" -eq 12
! grep -Fx teams "$qs_evidence/authoritative-modules.txt"

{
  printf 'qs_repo=%q\n' "$qs_repo"
  printf 'qs_source=%q\n' "$qs_source"
  printf 'qs_version=%q\n' "$qs_version"
  printf 'qs_origin=%q\n' "$qs_origin"
  printf 'qs_venv=%q\n' "$qs_venv"
  printf 'qs_python=%q\n' "$qs_python"
  printf 'qs_plan=%q\n' "$qs_plan"
  printf 'qs_backup_ref=%q\n' "$qs_backup_ref"
  printf 'qs_evidence=%q\n' "$qs_evidence"
  declare -p qs_modules
} > "$qs_evidence/session.env"

(
  cd "$qs_repo"
  poetry run pytest scripts/test_publish_module.py \
    quickscale_core/tests/test_git_utils.py -q --no-cov \
    | tee "$qs_evidence/focused-tests.log"
  make version-check 2>&1 | tee "$qs_evidence/version-check.log"
  make check QUIET=1 2>&1 | tee "$qs_evidence/check.log"
  set +e
  make quality > "$qs_evidence/quality.log" 2>&1
  quality_rc=$?
  set -e
  test "$quality_rc" -eq 2
  "$qs_python" - <<'PY'
import json
from pathlib import Path

report = json.loads(Path('.quickscale/quality_report.json').read_text())
regressions = report['regressions']
assert regressions['total_count'] == 1
assert regressions['warning_count'] == 1
assert regressions['critical_count'] == 0
rows = regressions['complexity']['new_or_worse']
assert len(rows) == 1
row = rows[0]
assert row['symbol'] == '_execute_apply_steps_locked'
assert row['complexity'] == 56
assert row['allowed_max_complexity'] == 55
status = json.loads(Path('.quickscale/quality_gate_status.json').read_text())
assert status['monotonicity_verdict'] == 'pass'
assert status['monotonicity_waiver_count'] == 0
PY
  cp .quickscale/quality_report.json "$qs_evidence/quality_report.json"
  cp .quickscale/quality_gate_status.json "$qs_evidence/quality_gate_status.json"
)
```

The focused tests, version check, and check target must exit `0`. `make quality` must exit
exactly `2`, and its generated JSON—not a transcribed expectation—is the oracle owning the
one-regression set at the phase-1 binding point. The inline Python assertion compares that
captured report to the accepted SA140 tuple.

**ABORT CONDITIONS:** Wrong path/HEAD/version/origin; any worktree delta outside this plan;
executable drift; inventory count/name failure; focused validation failure; or quality output
differing from the one accepted SA140 result. Do not repair any failure in this ceremony.

**VALIDATION CHECKPOINT:** `source-status.txt`, `authoritative-modules.txt`, the three exit-0
logs, and the parsed quality JSON all pass. Oracle provenance: Git and `VERSION` own identity,
`authoritative_module_names()` owns the module set when captured, and the quality target's
generated JSON owns its runtime result; the shell/Python assertions bind and compare them.

**STOP CONDITION:** Phase 1 stops before any ref mutation. Continue only with all assertions
green and the evidence directory retained.

**COLLAPSE:** forbidden; identity and baseline validation must precede every mutation.

## Phase 2 — Prove corrected-source trees equal the published split roots

**PHASE GOAL:** Implement resumption step 2 without republishing: bind each corrected-source
module root tree to the fresh remote split-branch root and prove the exact pre-delete branch
set and absence of split tags.

**SCOPE_IN:** Read corrected-source trees and remote refs; write evidence files; update only
`FETCH_HEAD`/local object storage through no-tag fetches. No branch/tag push or ref update.

**LIKELY FILES/SYMBOLS:** Read-only `quickscale_modules/<module>/module.yml`; remote
`refs/heads/splits/*` and `refs/tags/splits/*`.

**EXECUTION MODE:** serial.

**DEPENDS ON:** Phase 1.

**COMMANDS AND EXPECTED RESULTS:**

```bash
: > "$qs_evidence/expected-heads-before-teams-delete.txt"
for module in "${qs_modules[@]}"; do
  printf 'refs/heads/splits/%s-module\n' "$module" \
    >> "$qs_evidence/expected-heads-before-teams-delete.txt"
done
printf 'refs/heads/splits/teams-module\n' \
  >> "$qs_evidence/expected-heads-before-teams-delete.txt"
sort -o "$qs_evidence/expected-heads-before-teams-delete.txt" \
  "$qs_evidence/expected-heads-before-teams-delete.txt"
git -C "$qs_repo" ls-remote --heads origin 'refs/heads/splits/*' \
  | cut -f2 | sort > "$qs_evidence/actual-heads-before-seal.txt"
diff -u "$qs_evidence/expected-heads-before-teams-delete.txt" \
  "$qs_evidence/actual-heads-before-seal.txt"

printf 'module\tsource_tree\tbranch_sha\tbranch_tree\tmanifest_version\n' \
  > "$qs_evidence/corrected-source-tree-parity.tsv"
for module in "${qs_modules[@]}"; do
  branch_ref="refs/heads/splits/${module}-module"
  source_tree=$(git -C "$qs_repo" rev-parse \
    "$qs_source:quickscale_modules/$module")
  row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
  if [[ ! "$row" =~ ^([0-9a-f]{40})[[:space:]]+$branch_ref$ ]]; then
    printf 'invalid remote row for %s: %s\n' "$branch_ref" "$row" >&2
    exit 1
  fi
  branch_sha=${BASH_REMATCH[1]}
  git -C "$qs_repo" fetch --no-tags origin "$branch_ref" >/dev/null
  test "$(git -C "$qs_repo" rev-parse 'FETCH_HEAD^{commit}')" = "$branch_sha"
  branch_tree=$(git -C "$qs_repo" rev-parse 'FETCH_HEAD^{tree}')
  test "$branch_tree" = "$source_tree"
  git -C "$qs_repo" show "$qs_source:quickscale_modules/$module/module.yml" \
    > "$qs_evidence/${module}.source.module.yml"
  git -C "$qs_repo" show "$branch_sha:module.yml" \
    > "$qs_evidence/${module}.branch.module.yml"
  cmp "$qs_evidence/${module}.source.module.yml" \
    "$qs_evidence/${module}.branch.module.yml"
  manifest_version=$("$qs_python" -c \
    'import sys,yaml; print(yaml.safe_load(sys.stdin)["version"])' \
    < "$qs_evidence/${module}.branch.module.yml")
  test "$manifest_version" = "$qs_version"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$module" "$source_tree" "$branch_sha" "$branch_tree" "$manifest_version" \
    >> "$qs_evidence/corrected-source-tree-parity.tsv"
done
test "$(wc -l < "$qs_evidence/corrected-source-tree-parity.tsv")" -eq 13

git -C "$qs_repo" ls-remote --refs --tags origin 'refs/tags/splits/*' \
  | tee "$qs_evidence/preexisting-split-tags.txt"
test ! -s "$qs_evidence/preexisting-split-tags.txt"
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin \
  "refs/tags/$qs_version")"
```

**ABORT CONDITIONS:** A remote query does not return exactly one complete SHA; the remote
branch set is not exactly the twelve authoritative branches plus teams; any source/branch
tree differs; any manifest differs byte-for-byte or has the wrong version; any split tag or
remote core tag already exists. A tree mismatch requires a separate corrected-source
republish plan and independent review; this plan authorizes no `publish-module` call.

**VALIDATION CHECKPOINT:** The 13-line parity TSV has twelve data rows, every source tree
equals its fetched branch root, every manifest comparison succeeds, the exact branch-set
diff is empty, and split/core tag queries are empty. Oracle provenance: the corrected commit
owns source trees/manifests; each fresh `ls-remote` row owns its branch SHA at capture;
fetched Git objects own branch trees/manifests; `diff`, `test`, and `cmp` assert parity.

**STOP CONDITION:** No republish occurred. Continue only on exact equality.

**COLLAPSE:** forbidden; the no-republish decision must be proven before tag rebinding.

## Phase 3 — Preserve the prior tag object, rebind, and obtain a clean branch proof

**PHASE GOAL:** Implement resumption step 3: preserve the current annotated core-tag object
behind an explicit backup ref before any rebind, atomically rebind the local tag to corrected
source, keep it unpushed, and run a clean installed all-module apply with twelve branch
overrides.

**SCOPE_IN:** Local backup/tag refs; temporary detached source worktree and installed fixture;
exact verifier-owned Docker resources; retained logs. No remote mutation.

**LIKELY FILES/SYMBOLS:** Local `refs/tags/0.87.0`,
`refs/sa117e4-backup/core-tag/0.87.0`, `provision_installed_venv.sh`, installed `quickscale`,
apply prompt seams, and verifier cleanup helpers. No repository files may change.

**EXECUTION MODE:** serial.

**DEPENDS ON:** Phase 2.

**COMMANDS AND EXPECTED RESULTS — backup and rebind:**

```bash
tag_ref="refs/tags/$qs_version"
zero_oid=0000000000000000000000000000000000000000
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin "$tag_ref")"

if git -C "$qs_repo" show-ref --verify --quiet "$qs_backup_ref"; then
  prior_tag_object=$(git -C "$qs_repo" rev-parse "$qs_backup_ref")
  git -C "$qs_repo" cat-file -e "$prior_tag_object^{tag}"
else
  prior_tag_object=$(git -C "$qs_repo" rev-parse "$tag_ref^{tag}")
  prior_tag_commit=$(git -C "$qs_repo" rev-parse "$tag_ref^{commit}")
  printf 'tag_ref\tprior_tag_object\tprior_tag_commit\tbackup_ref\n' \
    > "$qs_evidence/core-tag-backup.tsv"
  printf '%s\t%s\t%s\t%s\n' \
    "$tag_ref" "$prior_tag_object" "$prior_tag_commit" "$qs_backup_ref" \
    >> "$qs_evidence/core-tag-backup.tsv"
  git -C "$qs_repo" update-ref "$qs_backup_ref" "$prior_tag_object" "$zero_oid"
fi
test "$(git -C "$qs_repo" rev-parse "$qs_backup_ref")" = "$prior_tag_object"
git -C "$qs_repo" cat-file -e "$qs_backup_ref^{tag}"

restore_prior_core_tag() {
  rc=$?
  if test "${core_tag_restore_armed:-0}" -eq 1; then
    git -C "$qs_repo" update-ref "$tag_ref" "$prior_tag_object" || true
  fi
  return "$rc"
}
core_tag_restore_armed=1
trap restore_prior_core_tag EXIT
git -C "$qs_repo" tag -f -a "$qs_version" "$qs_source" \
  -m "QuickScale $qs_version"
test "$(git -C "$qs_repo" rev-parse "$tag_ref^{commit}")" = "$qs_source"
test "$(git -C "$qs_repo" cat-file -t "$tag_ref")" = tag
test "$(git -C "$qs_repo" rev-parse "$qs_backup_ref")" = "$prior_tag_object"
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin "$tag_ref")"
core_tag_restore_armed=0
trap - EXIT

{
  printf 'tag_ref\tnew_tag_object\tnew_tag_commit\tbackup_ref\tprior_tag_object\n'
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$tag_ref" "$(git -C "$qs_repo" rev-parse "$tag_ref^{tag}")" \
    "$(git -C "$qs_repo" rev-parse "$tag_ref^{commit}")" \
    "$qs_backup_ref" "$prior_tag_object"
} > "$qs_evidence/core-tag-rebind.tsv"
```

Creating and verifying the backup ref precedes `git tag -f`. The EXIT obligation restores
the exact prior tag object if any rebind assertion fails. On success the backup ref remains
retained through SA117e-5; do not delete or push it.

**COMMANDS AND EXPECTED RESULTS — corrected-source prompt binding and branch apply:**

```bash
branch_parent=$(mktemp -d /tmp/quickscale-sa117e4-branch-proof-XXXXXX)
branch_source="$branch_parent/source"
branch_output="$branch_parent/installed"
git -C "$qs_repo" worktree add --detach "$branch_source" "$qs_source"
mkdir "$branch_output"
"$branch_source/scripts/provision_installed_venv.sh" \
  "$branch_source" "$branch_output" \
  > "$qs_evidence/branch-provision.stdout" \
  2> "$qs_evidence/branch-provision.stderr"
test "$(cat "$qs_evidence/branch-provision.stdout")" = "$branch_output"
branch_qs="$branch_output/venv/bin/quickscale"
branch_work="$branch_output/work"
test -x "$branch_qs"

set +e
(
  cd "$branch_work"
  printf '\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n' \
    | env -u PYTHONPATH -u PYTHONHOME "$branch_qs" plan testproj
) > "$qs_evidence/branch-plan.log" 2>&1
branch_plan_rc=$?
set -e
test "$branch_plan_rc" -eq 0
QS_PLAN_LOG="$qs_evidence/branch-plan.log" "$qs_python" - <<'PY'
import os
from pathlib import Path

text = Path(os.environ['QS_PLAN_LOG']).read_text()
prompts = (
    'Python package name',
    'Enter theme number or name',
    'Select modules',
    'Start Docker services after apply?',
    'Build Docker images?',
    'Create Django superuser?',
    'Save configuration?',
)
assert all(text.count(prompt) == 1 for prompt in prompts)
assert 'Traceback (most recent call last)' not in text
PY
QS_MODULES="${qs_modules[*]}" "$qs_python" - <<PY
import os
from pathlib import Path
import yaml

data = yaml.safe_load(Path('$branch_work/testproj/quickscale.yml').read_text())
assert set(data['modules']) == set(os.environ['QS_MODULES'].split())
PY

split_args=()
for module in "${qs_modules[@]}"; do
  split_args+=(--split-ref "$module=splits/${module}-module")
done
branch_compose=$("$qs_python" -c \
  'from scripts.verify_public_module_apply import generate_compose_project_name; print(generate_compose_project_name())')
branch_project="$branch_work/testproj"
branch_cleanup_armed=1
cleanup_branch_compose() {
  rc=$?
  if test "${branch_cleanup_armed:-0}" -eq 1; then
    QS_PROJECT="$branch_project" QS_COMPOSE="$branch_compose" "$qs_python" - <<'PY'
import os
from pathlib import Path
from scripts.verify_public_module_apply import cleanup_compose_project
cleanup_compose_project(Path(os.environ['QS_PROJECT']), os.environ['QS_COMPOSE'])
PY
  fi
  return "$rc"
}
trap cleanup_branch_compose EXIT
set +e
(
  cd "$branch_project"
  printf 'n\ny\ny\n' | env -u PYTHONPATH -u PYTHONHOME \
    QUICKSCALE_DEBUG=1 QUICKSCALE_VERIFY_COMPOSE_PROJECT="$branch_compose" \
    timeout --foreground 1800 "$branch_qs" apply "${split_args[@]}"
) > "$qs_evidence/branch-override-apply.log" 2>&1
branch_apply_rc=$?
set -e
cleanup_branch_compose
branch_cleanup_armed=0
trap - EXIT
test "$branch_apply_rc" -eq 0
QS_APPLY_LOG="$qs_evidence/branch-override-apply.log" "$qs_python" - <<'PY'
import os
from pathlib import Path

text = Path(os.environ['QS_APPLY_LOG']).read_text()
prompts = (
    'Show Docker build output?',
    'Proceed with apply?',
    'Proceed with destructive/remote operations?',
)
assert all(text.count(prompt) == 1 for prompt in prompts)
assert 'KeyError' not in text
assert 'Traceback (most recent call last)' not in text
PY
test -s "$branch_project/.quickscale/state.yml"

git -C "$qs_repo" worktree remove "$branch_source"
rm -rf "$branch_parent"
```

The plan sequence supplies seven responses and the log must contain each of the seven
corrected-source prompts exactly once. The apply sequence supplies three responses and the
log must contain each of the three corrected-source prompts exactly once. Those exact-count
assertions plus exit `0` prove the historical stdin bytes were fully consumed by the current
prompt contract rather than silently shifted or left over. The final `y` crosses the late
destructive gate; a retained `n` there would instead exit `1` after steps 1–10 and is not a
clean proof.

**ABORT CONDITIONS:** Missing/non-annotated local tag; inability to create or verify the
backup ref; remote core tag presence; failed rebind; provision/plan/apply nonzero; prompt
count drift; module-set mismatch; traceback/`KeyError`; missing state; or cleanup failure.
Retain the exact fixture on proof failure. The tag trap restores the old object only for an
incomplete rebind; do not improvise tag rollback after a successful phase.

**VALIDATION CHECKPOINT:** Backup/rebind TSVs prove both tag objects and corrected commit;
remote core-tag query remains empty; installed branch apply exits `0`, consumes exactly the
current seven-plus-three prompts, has all twelve branch overrides, emits no traceback or
`KeyError`, writes state, and exact Compose cleanup runs. Oracle provenance: Git refs own tag
identity at capture; corrected prompt implementations E-09/E-10 own prompt names/counts;
installed process exit/log/state own behavior; assertions compare each captured artifact.

**STOP CONDITION:** Corrected local tag is present and unpushed, prior tag object is retained,
and clean branch proof passes. No split tag exists yet.

**COLLAPSE:** forbidden; the reversible local rebind and clean branch proof must finish before
preparing an immutable seal.

## Phase 4 — Recapture, digest, and stop for fresh pre-seal confirmation

**PHASE GOAL:** Implement resumption step 4: recapture all twelve complete branch SHAs and
corrected-source parity, freeze the exact table and digest, and stop for a new maintainer
confirmation before any seal.

**SCOPE_IN:** Read source/remote; write pre-seal artifacts and one human confirmation record.
No tag push or remote mutation.

**LIKELY FILES/SYMBOLS:** Twelve source/remote manifests, twelve split branches, twelve target
split-tag refs, local core tag, pre-seal table/digest.

**EXECUTION MODE:** serial.

**DEPENDS ON:** Phase 3.

**COMMANDS AND EXPECTED RESULTS — capture and freeze:**

```bash
collect_corrected_preseal_table() {
  output=$1
  printf 'module\tbranch_sha\tsource_tree\tbranch_tree\tmanifest_version\ttag_state\n' \
    > "$output"
  for module in "${qs_modules[@]}"; do
    branch_ref="refs/heads/splits/${module}-module"
    tag_ref="refs/tags/splits/${module}-module/${qs_version}"
    row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
    [[ "$row" =~ ^([0-9a-f]{40})[[:space:]]+$branch_ref$ ]]
    branch_sha=${BASH_REMATCH[1]}
    tag_row=$(git -C "$qs_repo" ls-remote --refs --tags origin "$tag_ref")
    test -z "$tag_row"
    git -C "$qs_repo" fetch --no-tags origin "$branch_ref" >/dev/null
    test "$(git -C "$qs_repo" rev-parse 'FETCH_HEAD^{commit}')" = "$branch_sha"
    source_tree=$(git -C "$qs_repo" rev-parse \
      "$qs_source:quickscale_modules/$module")
    branch_tree=$(git -C "$qs_repo" rev-parse 'FETCH_HEAD^{tree}')
    test "$branch_tree" = "$source_tree"
    git -C "$qs_repo" show "$qs_source:quickscale_modules/$module/module.yml" \
      > "$qs_evidence/${module}.preseal.source.module.yml"
    git -C "$qs_repo" show "$branch_sha:module.yml" \
      > "$qs_evidence/${module}.preseal.branch.module.yml"
    cmp "$qs_evidence/${module}.preseal.source.module.yml" \
      "$qs_evidence/${module}.preseal.branch.module.yml"
    manifest_version=$("$qs_python" -c \
      'import sys,yaml; print(yaml.safe_load(sys.stdin)["version"])' \
      < "$qs_evidence/${module}.preseal.branch.module.yml")
    test "$manifest_version" = "$qs_version"
    printf '%s\t%s\t%s\t%s\t%s\tabsent\n' \
      "$module" "$branch_sha" "$source_tree" "$branch_tree" "$manifest_version" \
      >> "$output"
  done
  test "$(wc -l < "$output")" -eq 13
}

collect_corrected_preseal_table "$qs_evidence/preseal.tsv"
git -C "$qs_repo" ls-remote --refs --tags origin 'refs/tags/splits/*' \
  > "$qs_evidence/preseal-all-split-tags.txt"
test ! -s "$qs_evidence/preseal-all-split-tags.txt"
test "$(git -C "$qs_repo" rev-parse "refs/tags/$qs_version^{commit}")" \
  = "$qs_source"
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin \
  "refs/tags/$qs_version")"
sha256sum "$qs_evidence/preseal.tsv" \
  | tee "$qs_evidence/preseal.tsv.sha256"
cat "$qs_evidence/preseal.tsv"
cat "$qs_evidence/preseal.tsv.sha256"
```

**MANDATORY HUMAN STOP:** Stop here. Do not run phase 5. The maintainer must inspect all
twelve full SHAs, source/branch tree equality, manifest version `0.87.0`, byte-parity
evidence, and tag absence, then explicitly confirm the displayed table's digest. This plan
and its review provide no confirmation.

Only after that fresh decision, record it with this literal interaction:

```bash
preseal_digest=$(cut -d' ' -f1 "$qs_evidence/preseal.tsv.sha256")
read -r -p "Maintainer identity: " preseal_maintainer
test -n "$preseal_maintainer"
read -r -p \
  "Type $preseal_digest to confirm all 12 corrected-source pre-seal rows: " \
  preseal_typed_digest
test "$preseal_typed_digest" = "$preseal_digest"
preseal_confirmed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  printf 'gate=corrected-source-preseal\n'
  printf 'maintainer=%s\n' "$preseal_maintainer"
  printf 'confirmed_at=%s\n' "$preseal_confirmed_at"
  printf 'table=%s\n' "$qs_evidence/preseal.tsv"
  printf 'sha256=%s\n' "$preseal_digest"
  printf 'rows=12\n'
  printf 'version=%s\n' "$qs_version"
} > "$qs_evidence/preseal-confirmation.txt"
```

**ABORT CONDITIONS:** Any query/parity/version/tag/core-tag assertion fails; table does not
have exactly twelve rows; digest cannot be captured; maintainer declines, does not inspect
the complete rows, or does not type the exact digest. Recapture from scratch after any
branch movement; an earlier table or confirmation is void.

**VALIDATION CHECKPOINT:** `preseal.tsv`, its SHA-256 sidecar, twelve source/branch manifests,
empty all-split-tag capture, and confirmation record bind the exact approved set before
mutation. Oracle provenance: fresh remote rows/source Git objects own values at capture;
SHA-256 binds the frozen table; the maintainer's exact digest entry binds authorization;
shell assertions compare all values.

**STOP CONDITION:** Without `preseal-confirmation.txt`, execution stops. With it, proceed
directly to phase 5; do not reinterpret or regenerate the authorized rows.

**COLLAPSE:** forbidden; this human gate must remain a visible stop before immutable pushes.

## Phase 5 — Seal, verify, then separately confirm teams deletion

**PHASE GOAL:** Implement resumption step 5: revalidate the frozen authorized values, seal
twelve immutable split tags, verify exact refs/manifests/no-trigger evidence and a clean
default installed apply through both the approved harness and an exact final prompt-bound
no-override invocation, then retain a durable teams restoration ref before requesting and
executing the separate teams deletion confirmation.

**SCOPE_IN:** Twelve explicit namespaced split-tag pushes; remote/tag/manifest verification;
approved-harness and isolated prompt-bound installed default applies; retained prompt,
response-consumption, exit, traceback, and state evidence; local
`refs/sa117e4-backup/teams-branch/0.87.0`; one separately leased deletion of the teams branch.
No core-tag push or repository file edit.

**LIKELY FILES/SYMBOLS:** `Makefile` seal targets, `publish_module.py` seal-all path,
namespaced split refs, publication workflow trigger, approved apply harness, corrected-source
apply prompt seams, local teams backup ref, and teams branch.

**EXECUTION MODE:** serial.

**DEPENDS ON:** Phase 4's fresh confirmation.

**COMMANDS AND EXPECTED RESULTS — revalidate the authorized table:**

```bash
test -s "$qs_evidence/preseal-confirmation.txt"
preseal_digest=$(cut -d' ' -f1 "$qs_evidence/preseal.tsv.sha256")
test "$(sha256sum "$qs_evidence/preseal.tsv" | cut -d' ' -f1)" \
  = "$preseal_digest"
grep -Fx "sha256=$preseal_digest" "$qs_evidence/preseal-confirmation.txt"

verify_authorized_seal_state() {
  while IFS=$'\t' read -r module branch_sha source_tree branch_tree \
    manifest_version tag_state; do
    test "$module" != module || continue
    test "$manifest_version" = "$qs_version"
    test "$tag_state" = absent
    test "$source_tree" = "$branch_tree"
    branch_ref="refs/heads/splits/${module}-module"
    tag_ref="refs/tags/splits/${module}-module/${qs_version}"
    row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
    test "$row" = "$branch_sha"$'\t'"$branch_ref"
    tag_rows=$(git -C "$qs_repo" ls-remote --tags origin \
      "$tag_ref" "${tag_ref}^{}")
    if test -n "$tag_rows"; then
      peeled=$(git -C "$qs_repo" ls-remote --tags origin "${tag_ref}^{}")
      test "$peeled" = "$branch_sha"$'\t'"${tag_ref}^{}"
    fi
  done < "$qs_evidence/preseal.tsv"
}
verify_authorized_seal_state
```

The same verifier runs immediately before every initial or retry seal invocation. It permits
only absent tags or already-pushed annotated tags peeled to the frozen authorized commit.
Any branch movement voids the confirmation. The remaining reread-to-push race is the
explicitly accepted client-side residual in `decisions.md`; post-seal comparison still
fails closed and no pushed tag is moved.

**COMMANDS AND EXPECTED RESULTS — seal:**

```bash
seal_parent=$(mktemp -d /tmp/quickscale-sa117e4-seal-XXXXXX)
seal_source="$seal_parent/source"
git -C "$qs_repo" worktree add --detach "$seal_source" "$qs_source"
ln -s "$qs_venv" "$seal_source/.venv"
test -z "$(git -C "$seal_source" status --porcelain)"
test "$(git -C "$seal_source" rev-parse HEAD)" = "$qs_source"
test "$(git -C "$seal_source" rev-parse \
  "refs/tags/$qs_version^{commit}")" = "$qs_source"

(
  cd "$seal_source"
  env -u EXPECTED_REMOTE_SHA -u ABSENT -u PREVIOUS_VERSION \
    make seal-status VERSION="$qs_version"
  env -u EXPECTED_REMOTE_SHA -u ABSENT -u PREVIOUS_VERSION \
    make seal-modules VERSION="$qs_version"
) 2>&1 | tee "$qs_evidence/seal.log"

unlink "$seal_source/.venv"
git -C "$qs_repo" worktree remove "$seal_source"
rmdir "$seal_parent"
```

Both make targets must exit `0`. `VERSION` is the sole seal input; no previous version,
expected remote SHA, or absent sentinel is present. If seal-all stops partway, retain
`seal.log`, run `verify_authorized_seal_state`, diagnose, and rerun this seal block from a
fresh detached worktree. Existing correct tags are accepted. Never move a pushed tag.

**COMMANDS AND EXPECTED RESULTS — exact refs, manifests, and no-trigger proof:**

```bash
: > "$qs_evidence/expected-tags.txt"
for module in "${qs_modules[@]}"; do
  printf 'refs/tags/splits/%s-module/%s\n' "$module" "$qs_version" \
    >> "$qs_evidence/expected-tags.txt"
done
sort -o "$qs_evidence/expected-tags.txt" "$qs_evidence/expected-tags.txt"
git -C "$qs_repo" ls-remote --refs --tags origin 'refs/tags/splits/*' \
  | cut -f2 | sort > "$qs_evidence/actual-tags.txt"
diff -u "$qs_evidence/expected-tags.txt" "$qs_evidence/actual-tags.txt"

while IFS=$'\t' read -r module authorized_sha source_tree branch_tree \
  manifest_version tag_state; do
  test "$module" != module || continue
  branch_ref="refs/heads/splits/${module}-module"
  tag_ref="refs/tags/splits/${module}-module/${qs_version}"
  branch_row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
  test "$branch_row" = "$authorized_sha"$'\t'"$branch_ref"
  peeled_row=$(git -C "$qs_repo" ls-remote --tags origin "${tag_ref}^{}")
  test "$peeled_row" = "$authorized_sha"$'\t'"${tag_ref}^{}"
  git -C "$qs_repo" fetch --no-tags origin "$branch_ref" >/dev/null
  git -C "$qs_repo" show "$authorized_sha:module.yml" \
    > "$qs_evidence/${module}.sealed.module.yml"
  cmp "$qs_evidence/${module}.preseal.source.module.yml" \
    "$qs_evidence/${module}.sealed.module.yml"
  grep -q '^derivation:' "$qs_evidence/${module}.sealed.module.yml"
done < "$qs_evidence/preseal.tsv"

test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin \
  "refs/tags/$qs_version")"
test "$(git -C "$qs_repo" rev-parse \
  "refs/tags/$qs_version^{commit}")" = "$qs_source"

git -C "$qs_repo" show "$qs_source:.github/workflows/publish.yml" \
  > "$qs_evidence/publish-workflow.yml"
grep -Fx '      - "[0-9]*"' "$qs_evidence/publish-workflow.yml"
grep -Fx '      - "v[0-9]*"' "$qs_evidence/publish-workflow.yml"
while IFS= read -r ref; do
  tag=${ref#refs/tags/}
  case "$tag" in
    splits/*) ;;
    *) printf 'non-namespaced tag in seal set: %s\n' "$tag" >&2; exit 1 ;;
  esac
  case "$tag" in
    [0-9]*|v[0-9]*) printf 'PyPI-triggering tag: %s\n' "$tag" >&2; exit 1 ;;
    *) ;;
  esac
done < "$qs_evidence/actual-tags.txt"
{
  printf 'corrected_source=%s\n' "$qs_source"
  printf 'workflow_patterns=[0-9]*,v[0-9]*\n'
  printf 'seal_tag_prefix=splits/\n'
  printf 'remote_core_tag=absent\n'
  printf 'pypi_action=not-invoked\n'
} > "$qs_evidence/no-pypi-trigger.txt"
```

The exact expected-tag file is generated from the frozen authoritative inventory; the
remote supplies the actual set after sealing; `diff` asserts no missing or unexpected split
tag. The frozen pre-seal table owns every expected commit, and the workflow file at corrected
source owns trigger patterns. Ref-shape assertions plus remote core-tag absence prove this
ceremony emitted no tag that can trigger the PyPI workflow.

**COMMANDS AND EXPECTED RESULTS — approved harness and exact final default no-override apply:**

The previously approved harness byte identities are inline authority from the independent
historical harness review:

```text
verify_public_module_apply.py  b1fb28ff15da7159bb35421c26a1a5f9dd53e4561031ae6d244d58b8ece522ac
verify_sa117_publication.py    5fe178d94316e51ad462351a468a657a77735116afdcc4e8ce1f093a40dee5cc
```

Bind those approved values to corrected source before invoking the harness. Any drift stops
for independent harness re-review. The approved harness remains a mandatory acceptance run.
Because E-11 establishes that its success JSON does not expose the child prompt transcript
or stdin-consumption evidence, a separate isolated project then performs the exact final
default no-override invocation under an inline prompt-bound driver without weakening or
replacing any harness assertion.

```bash
test "$(git -C "$qs_repo" show \
  "$qs_source:scripts/verify_public_module_apply.py" | sha256sum | cut -d' ' -f1)" \
  = b1fb28ff15da7159bb35421c26a1a5f9dd53e4561031ae6d244d58b8ece522ac
test "$(git -C "$qs_repo" show \
  "$qs_source:scripts/verify_sa117_publication.py" | sha256sum | cut -d' ' -f1)" \
  = 5fe178d94316e51ad462351a468a657a77735116afdcc4e8ce1f093a40dee5cc

final_parent=$(mktemp -d /tmp/quickscale-sa117e4-final-XXXXXX)
final_source="$final_parent/source"
final_output="$final_parent/installed"
git -C "$qs_repo" worktree add --detach "$final_source" "$qs_source"
mkdir "$final_output"
"$final_source/scripts/provision_installed_venv.sh" \
  "$final_source" "$final_output" \
  > "$qs_evidence/final-provision.stdout" \
  2> "$qs_evidence/final-provision.stderr"
test "$(cat "$qs_evidence/final-provision.stdout")" = "$final_output"
final_qs="$final_output/venv/bin/quickscale"
final_work="$final_output/work"

set +e
(
  cd "$final_work"
  printf '\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n' \
    | env -u PYTHONPATH -u PYTHONHOME "$final_qs" plan testproj
) > "$qs_evidence/final-plan.log" 2>&1
final_plan_rc=$?
set -e
test "$final_plan_rc" -eq 0
QS_PLAN_LOG="$qs_evidence/final-plan.log" "$qs_python" - <<'PY'
import os
from pathlib import Path
text = Path(os.environ['QS_PLAN_LOG']).read_text()
prompts = (
    'Python package name', 'Enter theme number or name', 'Select modules',
    'Start Docker services after apply?', 'Build Docker images?',
    'Create Django superuser?', 'Save configuration?',
)
assert all(text.count(prompt) == 1 for prompt in prompts)
assert 'Traceback (most recent call last)' not in text
PY
QS_MODULES="${qs_modules[*]}" "$qs_python" - <<PY
import os
from pathlib import Path
import yaml
data = yaml.safe_load(Path('$final_work/testproj/quickscale.yml').read_text())
assert set(data['modules']) == set(os.environ['QS_MODULES'].split())
PY

set +e
(
  cd "$final_work"
  printf '\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n' \
    | env -u PYTHONPATH -u PYTHONHOME "$final_qs" plan promptproof
) > "$qs_evidence/final-prompt-proof-plan.log" 2>&1
final_prompt_plan_rc=$?
set -e
test "$final_prompt_plan_rc" -eq 0
QS_PLAN_LOG="$qs_evidence/final-prompt-proof-plan.log" "$qs_python" - <<'PY'
import os
from pathlib import Path
text = Path(os.environ['QS_PLAN_LOG']).read_text()
prompts = (
    'Python package name', 'Enter theme number or name', 'Select modules',
    'Start Docker services after apply?', 'Build Docker images?',
    'Create Django superuser?', 'Save configuration?',
)
assert all(text.count(prompt) == 1 for prompt in prompts)
assert 'Traceback (most recent call last)' not in text
PY
QS_MODULES="${qs_modules[*]}" "$qs_python" - <<PY
import os
from pathlib import Path
import yaml
data = yaml.safe_load(Path('$final_work/promptproof/quickscale.yml').read_text())
assert set(data['modules']) == set(os.environ['QS_MODULES'].split())
PY

env -u PYTHONPATH -u PYTHONHOME "$qs_python" \
  "$final_source/scripts/verify_public_module_apply.py" apply \
  --module analytics \
  --target "$final_work/testproj" \
  --executable "$final_qs" \
  --cwd "$final_work/testproj" \
  --timeout 1800 \
  --version "$qs_version" \
  --declared-origin "$qs_origin" \
  --expected-origin "$qs_origin" \
  --stdin $'n\ny\ny\n' \
  --argv quickscale apply \
  | tee "$qs_evidence/default-apply.json"

QS_DEFAULT_JSON="$qs_evidence/default-apply.json" "$qs_python" - <<'PY'
import json
import os
from pathlib import Path
data = json.loads(Path(os.environ['QS_DEFAULT_JSON']).read_text())
assert data['module'] == 'analytics'
assert data['version'] == '0.87.0'
assert data['argv'] == ['quickscale', 'apply']
assert data['origin_map_ok'] is True
assert data['exit_code'] == 0
assert data['state_digest']
PY
test -s "$final_work/testproj/.quickscale/state.yml"

prompt_project="$final_work/promptproof"
prompt_compose=$("$qs_python" -c \
  'from scripts.verify_public_module_apply import generate_compose_project_name; print(generate_compose_project_name())')
prompt_cleanup_armed=1
cleanup_prompt_compose() {
  rc=$?
  if test "${prompt_cleanup_armed:-0}" -eq 1; then
    QS_PROJECT="$prompt_project" QS_COMPOSE="$prompt_compose" "$qs_python" - <<'PY'
import os
from pathlib import Path
from scripts.verify_public_module_apply import cleanup_compose_project
cleanup_compose_project(Path(os.environ['QS_PROJECT']), os.environ['QS_COMPOSE'])
PY
  fi
  return "$rc"
}
trap cleanup_prompt_compose EXIT
set +e
QS_PROMPT_EXECUTABLE="$final_qs" \
QS_PROMPT_PROJECT="$prompt_project" \
QS_PROMPT_COMPOSE="$prompt_compose" \
QS_PROMPT_TRANSCRIPT="$qs_evidence/final-default-apply.transcript" \
QS_PROMPT_EVIDENCE="$qs_evidence/final-default-apply-interactions.json" \
  "$qs_python" - <<'PY'
import hashlib
import json
import os
import selectors
import subprocess
import time
from pathlib import Path

executable = Path(os.environ['QS_PROMPT_EXECUTABLE'])
project = Path(os.environ['QS_PROMPT_PROJECT'])
transcript_path = Path(os.environ['QS_PROMPT_TRANSCRIPT'])
evidence_path = Path(os.environ['QS_PROMPT_EVIDENCE'])
argv = [str(executable), 'apply']
expected = (
    (b'Show Docker build output?', b'n\n', 'n'),
    (b'Proceed with apply?', b'y\n', 'y'),
    (b'Proceed with destructive/remote operations?', b'y\n', 'y'),
)
env = os.environ.copy()
env.pop('PYTHONPATH', None)
env.pop('PYTHONHOME', None)
env['QUICKSCALE_DEBUG'] = '1'
env['QUICKSCALE_VERIFY_COMPOSE_PROJECT'] = os.environ['QS_PROMPT_COMPOSE']
transcript = bytearray()
exchanges = []
response_index = 0
stdin_closed_after_last_response = False
return_code = None
failure = None
deadline = time.monotonic() + 1800
process = subprocess.Popen(
    argv,
    cwd=project,
    env=env,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=0,
)
assert process.stdin is not None
assert process.stdout is not None
selector = selectors.DefaultSelector()
selector.register(process.stdout, selectors.EVENT_READ)
search_from = 0

def read_until(needle: bytes) -> None:
    global search_from
    while True:
        found = transcript.find(needle, search_from)
        if found >= 0:
            search_from = found + len(needle)
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f'timed out waiting for {needle!r}')
        if not selector.select(remaining):
            raise TimeoutError(f'timed out waiting for {needle!r}')
        chunk = os.read(process.stdout.fileno(), 4096)
        if not chunk:
            raise RuntimeError(f'child output ended before {needle!r}')
        transcript.extend(chunk)

try:
    for prompt, response, response_text in expected:
        read_until(prompt)
        process.stdin.write(response)
        process.stdin.flush()
        response_index += 1
        exchanges.append({
            'prompt': prompt.decode(),
            'response': response_text,
            'sent_after_prompt': True,
        })
    process.stdin.close()
    stdin_closed_after_last_response = True
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('timed out waiting for final default apply exit')
        events = selector.select(min(remaining, 0.25))
        if events:
            chunk = os.read(process.stdout.fileno(), 4096)
            if chunk:
                transcript.extend(chunk)
                continue
        if process.poll() is not None:
            while True:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                transcript.extend(chunk)
            break
    return_code = process.wait()
    state_path = project / '.quickscale' / 'state.yml'
    state_bytes = state_path.read_bytes()
    assert argv == [str(executable), 'apply']
    assert response_index == len(expected) == 3
    assert stdin_closed_after_last_response is True
    assert all(transcript.count(prompt) == 1 for prompt, _, _ in expected)
    assert b'Traceback (most recent call last)' not in transcript
    assert b'KeyError' not in transcript
    assert return_code == 0
    assert state_bytes
except BaseException as exc:
    failure = f'{type(exc).__name__}: {exc}'
    if process.poll() is None:
        process.kill()
    return_code = process.wait()
    raise
finally:
    transcript_path.write_bytes(transcript)
    state_path = project / '.quickscale' / 'state.yml'
    state_bytes = state_path.read_bytes() if state_path.is_file() else b''
    evidence = {
        'quickscale_argv': ['quickscale', 'apply'],
        'override_arguments': [],
        'prompt_source': 'corrected-source E-10 apply prompt contract',
        'exchanges': exchanges,
        'response_count': response_index,
        'pending_responses': len(expected) - response_index,
        'stdin_closed_after_last_response': stdin_closed_after_last_response,
        'prompt_occurrences': {
            prompt.decode(): transcript.count(prompt) for prompt, _, _ in expected
        },
        'exit_code': return_code,
        'traceback': b'Traceback (most recent call last)' in transcript,
        'key_error': b'KeyError' in transcript,
        'state_success': bool(state_bytes),
        'state_digest': hashlib.sha256(state_bytes).hexdigest() if state_bytes else None,
        'failure': failure,
    }
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
PY
prompt_apply_rc=$?
set -e
cleanup_prompt_compose
prompt_cleanup_armed=0
trap - EXIT
test "$prompt_apply_rc" -eq 0

QS_PROMPT_JSON="$qs_evidence/final-default-apply-interactions.json" \
QS_PROMPT_TRANSCRIPT="$qs_evidence/final-default-apply.transcript" \
  "$qs_python" - <<'PY'
import json
import os
from pathlib import Path

data = json.loads(Path(os.environ['QS_PROMPT_JSON']).read_text())
transcript = Path(os.environ['QS_PROMPT_TRANSCRIPT']).read_text()
prompts = (
    'Show Docker build output?',
    'Proceed with apply?',
    'Proceed with destructive/remote operations?',
)
assert data['quickscale_argv'] == ['quickscale', 'apply']
assert data['override_arguments'] == []
assert [row['prompt'] for row in data['exchanges']] == list(prompts)
assert [row['response'] for row in data['exchanges']] == ['n', 'y', 'y']
assert all(row['sent_after_prompt'] is True for row in data['exchanges'])
assert data['response_count'] == 3
assert data['pending_responses'] == 0
assert data['stdin_closed_after_last_response'] is True
assert data['prompt_occurrences'] == {prompt: 1 for prompt in prompts}
assert all(transcript.count(prompt) == 1 for prompt in prompts)
assert data['exit_code'] == 0
assert data['traceback'] is False
assert data['key_error'] is False
assert data['state_success'] is True
assert data['state_digest']
assert data['failure'] is None
PY
test -s "$prompt_project/.quickscale/state.yml"

git -C "$qs_repo" worktree remove "$final_source"
rm -rf "$final_parent"
```

The approved harness must exit `0`; its exact argv assertion proves its invocation has no
`--split-ref` or other QuickScale CLI override. Harness-owned JSON remains the oracle for its
argv, origin, state digest, exit, and exact Compose cleanup, so its historical acceptance is
not weakened. The separate isolated `promptproof` project is then the exact final default
no-override `quickscale apply` invocation. E-10 owns the ordered three-prompt contract at the
corrected-source binding point. The inline driver captures that invocation's combined output,
waits for each owned prompt before sending only its corresponding response (`n`, `y`, `y`),
closes stdin immediately after the third response, and records zero pending responses. Its
retained transcript and interaction JSON assert each prompt exactly once, the exact response
order, no shift or leftover input, exit `0`, no traceback/`KeyError`, and nonempty state with
a runtime digest. Any unexpected required prompt cannot receive input and therefore times out
rather than passing silently. Exit `0` from the still-mandatory approved harness closes
`SA117E3-PUBLIC-ANALYTICS-001`. On either failure, retain the exact fixture, JSON, transcript,
and logs.

**MANDATORY SECOND HUMAN STOP — teams deletion:** Only after every seal, approved-harness,
and exact final prompt-bound default-apply assertion above passes, freshly read teams state,
fetch and retain its exact commit under the named local backup ref, arm the restoration
record, show the exact SHA and anchor, and request a separate confirmation. The pre-seal
confirmation does not authorize this.

```bash
teams_ref=refs/heads/splits/teams-module
teams_backup_ref=refs/sa117e4-backup/teams-branch/0.87.0
teams_row=$(git -C "$qs_repo" ls-remote --refs origin "$teams_ref")
if [[ ! "$teams_row" =~ ^([0-9a-f]{40})[[:space:]]+$teams_ref$ ]]; then
  printf 'invalid teams row: %s\n' "$teams_row" >&2
  exit 1
fi
teams_sha=${BASH_REMATCH[1]}
git -C "$qs_repo" fetch --no-tags origin "$teams_ref" >/dev/null
test "$(git -C "$qs_repo" rev-parse 'FETCH_HEAD^{commit}')" = "$teams_sha"
zero_oid=0000000000000000000000000000000000000000
if git -C "$qs_repo" show-ref --verify --quiet "$teams_backup_ref"; then
  test "$(git -C "$qs_repo" rev-parse "$teams_backup_ref^{commit}")" \
    = "$teams_sha"
else
  git -C "$qs_repo" update-ref "$teams_backup_ref" "$teams_sha" "$zero_oid"
fi
test "$(git -C "$qs_repo" rev-parse "$teams_backup_ref^{commit}")" \
  = "$teams_sha"
git -C "$qs_repo" cat-file -e "$teams_backup_ref^{commit}"
{
  printf 'remote_ref=%s\n' "$teams_ref"
  printf 'authorized_sha=%s\n' "$teams_sha"
  printf 'backup_ref=%s\n' "$teams_backup_ref"
  printf 'backup_commit=%s\n' \
    "$(git -C "$qs_repo" rev-parse "$teams_backup_ref^{commit}")"
  printf 'lifecycle=retain-local-through-SA117e-5;never-push;explicit-maintainer-disposition-after-release-rollback-window\n'
} > "$qs_evidence/teams-backup-anchor.txt"
{
  printf 'ref=%s\n' "$teams_ref"
  printf 'authorized_sha=%s\n' "$teams_sha"
  printf 'backup_ref=%s\n' "$teams_backup_ref"
  printf 'lease=--force-with-lease=%s:%s\n' "$teams_ref" "$teams_sha"
  printf 'conditional_restore_refspec=%s:%s\n' \
    "$teams_backup_ref" "$teams_ref"
  printf 'conditional_restore=git -C %s push origin %s:%s\n' \
    "$qs_repo" "$teams_backup_ref" "$teams_ref"
} > "$qs_evidence/teams-delete-obligation.txt"
cat "$qs_evidence/teams-backup-anchor.txt"
cat "$qs_evidence/teams-delete-obligation.txt"

read -r -p "Maintainer identity for teams deletion: " teams_maintainer
test -n "$teams_maintainer"
read -r -p \
  "Type $teams_sha to confirm deletion of $teams_ref at that exact SHA: " \
  teams_typed_sha
test "$teams_typed_sha" = "$teams_sha"
teams_confirmed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  printf 'gate=teams-branch-delete\n'
  printf 'maintainer=%s\n' "$teams_maintainer"
  printf 'confirmed_at=%s\n' "$teams_confirmed_at"
  printf 'ref=%s\n' "$teams_ref"
  printf 'sha=%s\n' "$teams_sha"
  printf 'backup_ref=%s\n' "$teams_backup_ref"
} > "$qs_evidence/teams-delete-confirmation.txt"

git -C "$qs_repo" push \
  --force-with-lease="$teams_ref:$teams_sha" origin ":$teams_ref"
test -z "$(git -C "$qs_repo" ls-remote --refs origin "$teams_ref")"
test "$(git -C "$qs_repo" rev-parse "$teams_backup_ref^{commit}")" \
  = "$teams_sha"
```

The fresh remote row owns the authorized teams SHA. The no-tag fetch must materialize that
exact commit locally, and the named backup ref is created and verified against it before the
human confirmation and deletion. An already-existing anchor is accepted only if it resolves
to the same commit; a conflicting anchor aborts rather than moving retained rollback state.
The deletion uses the same frozen SHA the maintainer typed; it is not reread or substituted
after authorization. If the branch moves, the exact lease rejects deletion. The obligation
record exists before mutation and its restoration refspec sources the retained local backup
ref, not a potentially unavailable raw object name. Do not run that restoration automatically;
on a new maintainer decision, run the recorded `git push origin
refs/sa117e4-backup/teams-branch/0.87.0:refs/heads/splits/teams-module`. Successful teams
removal is the intended final state. Retain the local backup ref through SA117e-5, never push
the backup namespace itself, and dispose of it only by explicit maintainer decision after the
release rollback window.

**COMMANDS AND EXPECTED RESULTS — final exact state and evidence index:**

```bash
: > "$qs_evidence/expected-heads-final.txt"
for module in "${qs_modules[@]}"; do
  printf 'refs/heads/splits/%s-module\n' "$module" \
    >> "$qs_evidence/expected-heads-final.txt"
done
sort -o "$qs_evidence/expected-heads-final.txt" \
  "$qs_evidence/expected-heads-final.txt"
git -C "$qs_repo" ls-remote --heads origin 'refs/heads/splits/*' \
  | cut -f2 | sort > "$qs_evidence/actual-heads-final.txt"
diff -u "$qs_evidence/expected-heads-final.txt" \
  "$qs_evidence/actual-heads-final.txt"
git -C "$qs_repo" ls-remote --refs --tags origin 'refs/tags/splits/*' \
  | cut -f2 | sort > "$qs_evidence/actual-tags-final.txt"
diff -u "$qs_evidence/expected-tags.txt" \
  "$qs_evidence/actual-tags-final.txt"
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin \
  "refs/tags/$qs_version")"
test "$(git -C "$qs_repo" rev-parse \
  "refs/tags/$qs_version^{commit}")" = "$qs_source"
test "$(git -C "$qs_repo" rev-parse "$qs_backup_ref")" = "$prior_tag_object"
test "$(git -C "$qs_repo" rev-parse "$teams_backup_ref^{commit}")" \
  = "$teams_sha"
git -C "$qs_repo" cat-file -e "$teams_backup_ref^{commit}"
grep -Fx "backup_ref=$teams_backup_ref" "$qs_evidence/teams-backup-anchor.txt"
grep -Fx "backup_commit=$teams_sha" "$qs_evidence/teams-backup-anchor.txt"
grep -Fx \
  'lifecycle=retain-local-through-SA117e-5;never-push;explicit-maintainer-disposition-after-release-rollback-window' \
  "$qs_evidence/teams-backup-anchor.txt"

find "$qs_evidence" -type f ! -name SHA256SUMS -print0 \
  | sort -z | xargs -0 sha256sum > "$qs_evidence/SHA256SUMS"
test -s "$qs_evidence/SHA256SUMS"
printf 'SA117e-4 evidence retained at %s\n' "$qs_evidence"
```

**ABORT CONDITIONS:** Missing/mismatched confirmation; frozen table digest drift; branch
movement; seal failure/conflict; missing/unexpected tag or branch; manifest/derivation
mismatch; core tag observed remotely; harness hash drift; plan/apply/harness failure; prompt
drift; final interaction transcript/response binding/exit/traceback/state failure; teams row
ambiguity; teams fetch/object mismatch; missing or conflicting teams backup ref; teams lease
failure; backup lifecycle-evidence failure; or evidence-index failure. After any pushed split
tag, never move it. Diagnose and rerun only the reviewed idempotent seal/verification path.
Retain failed fixtures and all evidence.

**VALIDATION CHECKPOINT:** Twelve exact namespaced tags peel to the twelve authorized SHAs;
no unexpected split tag or branch exists; every sealed manifest is byte-identical to
corrected source and includes derivation; the local core tag targets corrected source and is
absent remotely; static/ref evidence proves no PyPI-triggering tag; the approved default
harness exits `0` with argv exactly `quickscale apply`; the separate exact final default
no-override invocation retains a transcript and interaction JSON proving each E-10 prompt
exactly once, responses `n/y/y` sent only after their prompts with zero pending input, exit
`0`, no traceback/`KeyError`, and state success; teams deletion has its own exact-SHA
confirmation/lease and a pre-deletion local backup ref verified to that SHA; final branch set
is exactly twelve. Oracle provenance: E-10 owns the prompt sequence at corrected-source
binding; the inline driver captures and controls the exact final invocation and asserts its
transcript/input queue/exit/state; the fresh teams row owns the deletion SHA, the no-tag fetch
materializes it, and Git's verified backup ref owns the restoration source before mutation.
Every other comparison names its emitting source, capture/freeze point, and asserting command
above.

**STOP CONDITION:** Phase 5 closes only when all final diffs/tests, exact final prompt-bound
evidence, both retained backup refs, and `SHA256SUMS` pass and the evidence root is retained.
Do not push the core tag or either backup namespace. Hand the evidence path to SA117e-5 and
the later SA96-PUBLISH gate.

**COLLAPSE:** forbidden; seal verification/default apply must complete before the separately
confirmed teams deletion.

## Rollback and interruption obligations

1. **Before local tag rebind:** the prior annotated tag object is preserved first at
   `refs/sa117e4-backup/core-tag/0.87.0`. An incomplete rebind restores the exact old object
   with `git update-ref refs/tags/0.87.0 "$prior_tag_object"`. Retain the backup through
   SA117e-5; never push it.
2. **Before seal:** no remote mutation exists to roll back. A failed tree/parity/human gate
   stops. Branch mismatch requires a new reviewed republish plan.
3. **During/after seal:** remote split tags are immutable. If interrupted, retain evidence,
   verify existing tags against the frozen table, and rerun seal-all; never move/delete a
   pushed tag. A conflicting/wrong tag is an escalation, not a rollback command.
4. **Temporary worktrees/fixtures:** arm exact-path cleanup before service-backed apply.
   Remove only the allocated path after success; retain it on diagnostic failure. Harness
   cleanup owns only its generated exact Compose project identity.
5. **Before teams deletion:** freshly capture the teams SHA, fetch and verify that exact commit,
   create or verify `refs/sa117e4-backup/teams-branch/0.87.0` at that SHA, and record its
   lifecycle, exact-SHA lease, confirmation, and restoration refspec
   `refs/sa117e4-backup/teams-branch/0.87.0:refs/heads/splits/teams-module` before deleting.
   The lease fails if the branch moves; the retained ref keeps the restoration object locally
   pushable after deletion. Restore only on a new maintainer decision, never as automatic
   cleanup. Retain the backup locally through SA117e-5, never push its namespace, and dispose
   of it only by explicit maintainer decision after the release rollback window.
6. **Core tag after successful seal:** keep corrected local `0.87.0` unpushed for the later
   release gate. Deleting/restoring it after immutable seal is not routine rollback and
   requires explicit maintainer direction informed by retained evidence.

## Final closeout evidence expectations

SA117e-4 is ready for SA117e-5 only when the retained evidence directory includes at least:

- source status, origin, frozen module inventory, focused validation logs, and parsed quality
  report/status;
- corrected-source tree-parity TSV and all source/branch manifests;
- core-tag backup and rebind TSVs proving prior object retention and corrected target;
- installed branch plan/apply logs with exact prompt-count and clean-exit assertions;
- twelve-row pre-seal TSV, digest, source/branch manifests, and fresh human confirmation;
- seal log, exact expected/actual tag sets, sealed manifests, workflow snapshot, and
  `no-pypi-trigger.txt`;
- approved-harness digest checks, final plan log, default-apply JSON with exact no-override
  argv and exit 0, and its state evidence;
- the separate exact final default no-override transcript and interaction JSON proving the
  three prompts exactly once, prompt-bound `n/y/y` responses with zero pending input, exit 0,
  no traceback/`KeyError`, and state success with a runtime digest;
- teams backup-anchor lifecycle evidence proving the named local ref resolves to the freshly
  confirmed SHA, the deletion obligation whose restoration refspec sources that anchor, the
  separate confirmation, exact final twelve-head and twelve-tag sets, and `SHA256SUMS`.

No evidence item authorizes the later core-tag push or a PyPI action.

## Risks and advisory hardening

- A split branch can move after confirmation. Immediate pre-seal revalidation and the seal's
  internal sample/reread minimize this, but client-side enforcement retains the explicitly
  accepted narrow race; post-seal mismatch is escalated without moving a tag.
- Partial seal leaves immutable correct tags. Treat this as resumable state, not rollback.
- Harness or prompt drift must stop for review; never edit stdin blindly. The separate final
  prompt-bound driver deliberately withholds each response until its owned prompt appears and
  times out on an unexpected required prompt; retain its transcript and JSON on failure.
- Docker/PostgreSQL are shared infrastructure. Serialize service-backed proof with other
  tracks and retain exact fixture identities on failure.
- The core-tag and teams-branch backup refs are local shared-repository state. Retain and never
  push them; SA117e-5 must record their disposition after the release lifecycle no longer
  needs rollback evidence. A conflicting pre-existing teams anchor blocks deletion rather
  than being moved silently.
- Force-privileged maintainers can bypass client-side tag immutability; this accepted residual
  does not justify weakening any normal-path check.

## Open questions

None. The only pending decisions are the two explicit execution-time human gates; neither is
pre-granted and neither blocks independent review of this plan.

## Mandatory pre-return self-review

This is author hardening, not the independent plan-review gate.

1. **Correctness/completeness — pass.** The revised objective states: “prove a clean default
   installed apply with exact prompt/response-consumption evidence” and “retain and verify a
   local restoration anchor before requesting a separate confirmation to delete the stale
   teams split branch,” while preserving the complete five-step outcome.
2. **Integration fit — pass.** Evidence E-03/E-04 and every phase bind the decisions order,
   Make targets, seal helper, inventory, installed entrypoint, workflow trigger, and remote
   refs; revised E-11 explicitly binds the approved harness limitation to the separate final
   prompt-proof mechanism rather than altering the harness.
3. **Compatibility/contracts — pass.** The plan changes no code contract and explicitly
   preserves “The core tag remains local and unpushed,” while verifying both branch-override
   and default immutable-tag consumption.
4. **Safety/boundaries — pass.** “Never run `git push --tags`,” “Pass neither
   `EXPECTED_REMOTE_SHA` nor `ABSENT` to a seal command,” and two distinct mandatory human
   stops make the outward boundaries explicit. Phase 5 additionally says “Do not push the
   core tag or either backup namespace.”
5. **Scope discipline — pass.** The out-of-scope list forbids repository edits, historical
   plan edits, unreviewed republish, core-tag push, and PyPI action; Phase 5 scopes only the
   new prompt evidence and local teams anchor required by F-001/F-002.
6. **Validation coverage — pass.** Phase 5 states that the inline driver “waits for each owned
   prompt before sending only its corresponding response (`n`, `y`, `y`), closes stdin
   immediately after the third response, and records zero pending responses,” then asserts
   exact prompt counts, exit `0`, no traceback, and state. It also requires the fresh teams
   commit to be fetched and the named anchor verified before deletion. Existing failure paths
   for branch movement, partial seal, tag conflict, harness drift, and lease failure remain.
7. **Caller parity — n/a.** No interface/signature/exported contract or same-fact repository
   artifact is changed; the plan only executes existing seams and verifies their parity.
8. **Invoked-behavior evidence — pass.** E-01 and E-04 through E-11 cite actual helper
   behavior. E-11 quotes the harness's output limitation, and the new prompt binding is
   implemented inline rather than assumed from a helper name.
9. **Cross-cutting hardening — pass.** Local patterns are reused, complete success/error/
   interruption paths are owned, publication and exact-lease boundaries are explicit, the
   teams restoration source is locally retained, and advisory residuals remain in risks
   without widening scope.
10. **Review-bar readiness — pass.** The criterion-by-criterion rubric results below quote
    the revised plan text. Independent Adaptive-plan-review must still return `STATUS: ok`
    before execution.

### Adaptive plan-review rubric verdicts

1. **Phase boundaries — pass.** Each numbered phase has an explicit stop; for example phase 4
   says: “Without `preseal-confirmation.txt`, execution stops,” and Phase 5 closes only when
   “exact final prompt-bound evidence, both retained backup refs, and `SHA256SUMS` pass.”
2. **Validation checkpoints — pass.** Phase 5 names the final invocation's oracle and binding:
   “E-10 owns the prompt sequence at corrected-source binding; the inline driver captures and
   controls the exact final invocation and asserts its transcript/input queue/exit/state.” It
   also states the concrete expected result: “each E-10 prompt exactly once, responses `n/y/y`
   sent only after their prompts with zero pending input, exit `0`, no traceback/`KeyError`,
   and state success.” Execute-capable SA117e-4 operators, not review agents, own commands.
3. **Rollback handling — pass.** Before teams mutation, Phase 5 says: “The no-tag fetch must
   materialize that exact commit locally, and the named backup ref is created and verified
   against it before the human confirmation and deletion,” and the obligation's restoration
   refspec “sources the retained local backup ref.” The exact prior core-tag restoration and
   immutable-tag non-rollback remain explicit.
4. **Phase-local scope — pass.** Every phase has `SCOPE_IN` and likely files/symbols; Phase 5
   now explicitly includes “local `refs/sa117e4-backup/teams-branch/0.87.0`” and “retained
   prompt, response-consumption, exit, traceback, and state evidence,” while still stating
   “No core-tag push or repository file edit.”
5. **Evidence grounding — pass.** The plan states
   “`snapshot_id=SA147-CORRECTED-PLAN-DISCOVERY-2026-08-15`, `snapshot_reused=true`.” Revised
   E-01 names the local-object prerequisite and E-11 states that the approved harness “does
   not expose successful-child prompt transcript or stdin-consumption evidence,” grounding
   both added mechanisms in the reused snapshot and reviewed source behavior.
6. **Contract-change handling — n/a.** The plan changes no interface, signature, schema, or
   exported contract; it consumes and verifies existing publication/apply contracts.
7. **Parallel-safe metadata — n/a.** Every phase says `EXECUTION MODE: serial`; no phase is
   labeled parallel-safe.

### Cross-cutting check verdicts

- **Consistency — pass.** “The approved harness remains a mandatory acceptance run,” while
  the isolated proof uses the existing installed CLI, prompt contract, and exact Compose
  cleanup seam; the teams anchor uses Git's existing local-ref mechanism rather than a new
  restoration store.
- **Completeness — pass.** The plan now owns the previously missing outcomes verbatim: the
  exact final invocation records “zero pending responses” plus prompt/exit/state evidence,
  and the teams obligation's restoration refspec “sources the retained local backup ref, not
  a potentially unavailable raw object name.” All previously passing five-step mechanisms,
  gates, aborts, rollback, and closeout evidence remain present.
- **Security boundaries — pass.** The plan retains “Never run `git push --tags`,” exact
  namespaced tags, absent remote core tag, no PyPI action, no seal authorization input,
  exact-SHA teams lease, and confirmation values frozen before mutation; it additionally says
  never to push either backup namespace.
- **Advisory hardening — pass.** The risks explicitly retain failed prompt evidence,
  serialize Docker/PostgreSQL use, preserve both backup refs, reject a conflicting teams
  anchor rather than moving it, and acknowledge the force-privileged and narrow race
  residuals without expanding implementation scope.

## FINDING STATUS

| finding_id | lifecycle state | successor IDs | revision disposition |
|---|---|---|---|
| F-001 | resolved | none | The revised plan specifies pre-deletion fetch/object verification, creation or exact-match verification of `refs/sa117e4-backup/teams-branch/0.87.0`, restoration from that ref, and final lifecycle/disposition evidence; independent review confirmation remains pending. |
| F-002 | resolved | none | The revised plan preserves the approved harness and specifies a separate exact final no-override invocation with prompt-bound response delivery, retained transcript/JSON, zero pending input, exit/no-traceback/state assertions, and closeout evidence; independent review confirmation remains pending. |

## CHANGED SECTIONS

- `Objective, scope, and fixed facts` — F-001, F-002.
- `Evidence ledger and authority` (E-01 and E-11 only) — F-001, F-002.
- `Phase 5 — Seal, verify, then separately confirm teams deletion` (goal, scope, likely seams,
  approved-harness/final-apply block, teams-deletion block, final evidence block, aborts,
  checkpoint, and stop condition) — F-001, F-002.
- `Rollback and interruption obligations` (item 5 only) — F-001.
- `Final closeout evidence expectations` — F-001, F-002.
- `Risks and advisory hardening` — F-001, F-002.
- `Mandatory pre-return self-review` and its rubric/cross-cutting verdicts — F-001, F-002.
- Every section not named above is preserved unchanged from DC-189.
