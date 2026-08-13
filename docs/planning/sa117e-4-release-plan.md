# SA117e-4 — Loop, Seal, and Human-Confirmed Publication

> **Status:** revised after independent review returned `STATUS: needs_changes`; awaiting
> independent re-review for `SA117E4-DRIFT-003`.
> **Frozen source:** `179ec3a8544d05a87a8574a4d6c37c4911ea6ad2`, the observed `v87`
> tip on 2026-08-13.
> **Scope:** [Module Version Lockstep](../technical/decisions.md#module-version-lockstep)
> steps 2–5. Step 6, pushing core tag `0.87.0`, remains with SA96-PUBLISH.

## Binding identity and lifecycle

| Input | Value |
|---|---|
| Frozen executable source | `179ec3a8544d05a87a8574a4d6c37c4911ea6ad2` |
| Repository version | `0.87.0` |
| Authoritative modules | `12` |
| Superseded input | `7c876308f6715321fa50fc5e5f36c9f3e0fc1080` |

This plan and its roadmap entry are intentionally uncommitted Phase 0 artifacts on the
`v87` worktree until SA117e-4 executes. They make that worktree dirty. **No publication
or seal command runs from that worktree or from `wt-track3`.** Every mutating command
below uses a clean disposable worktree detached at the frozen SHA. SA117e-5 owns the
documentation commit.

If `v87` advances, or any executable, package, or module path differs from the frozen
commit, stop and return the plan to independent review.

At authoring time, all twelve source manifests carry `0.87.0`; thirteen remote split
branches exist; no remote split tags or core tag `0.87.0` exist; and `make quality`
exits 2 only on the accepted SA140 complexity baseline.

## Binding decisions and review retrospective

- `make quality` exit 2 gates SA96-PUBLISH, not this child. Do not repair SA140 here.
- Delete orphan `refs/heads/splits/teams-module` after step 5, using a fresh exact-SHA
  lease and a separate maintainer confirmation. It is not sealed or included in the
  step-4 gate.
- The first review found that `git subtree --rejoin` advances `HEAD`, the shell loop
  was not fail-fast, the human-gate table was not executable, the installed-wheel
  fixture was implicit, the teams decision was unresolved, and the worktree was not
  actually clean. The procedures below address all six points.

## One-time setup

Run in Bash:

```bash
set -euo pipefail
qs_repo=/home/victor/code/quickscale
qs_frozen=179ec3a8544d05a87a8574a4d6c37c4911ea6ad2
qs_version=0.87.0
qs_origin=https://github.com/Experto-AI/quickscale.git
qs_venv="$qs_repo/.venv"
qs_evidence=$(mktemp -d /tmp/quickscale-sa117e4-evidence-XXXXXX)
qs_modules=(analytics auth backups billing blog crm forms listings \
  notifications orgs social storage)

test "${#qs_modules[@]}" -eq 12
test "$(git -C "$qs_repo" rev-parse v87)" = "$qs_frozen"
test "$(git -C "$qs_repo" show "$qs_frozen:VERSION")" = "$qs_version"
test -x "$qs_venv/bin/python"
git -C "$qs_repo" diff --quiet "$qs_frozen" -- \
  Makefile scripts quickscale quickscale_cli quickscale_core quickscale_modules
test -z "$(git -C "$qs_repo" status --porcelain --untracked-files=all -- \
  Makefile scripts quickscale quickscale_cli quickscale_core quickscale_modules)"
```

The last two checks permit the Phase 0 documentation delta but reject tracked or untracked
executable drift.
Preserve `$qs_evidence` through SA117e-5.

## Step 2 — local core tag only

```bash
if git -C "$qs_repo" rev-parse -q --verify "refs/tags/$qs_version" >/dev/null; then
  test "$(git -C "$qs_repo" rev-list -n 1 "$qs_version")" = "$qs_frozen"
else
  git -C "$qs_repo" tag -a "$qs_version" "$qs_frozen" \
    -m "QuickScale $qs_version"
fi
test "$(git -C "$qs_repo" rev-list -n 1 "$qs_version")" = "$qs_frozen"
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin \
  "refs/tags/$qs_version")"
```

Never run `git push --tags`. If steps 2–3 are abandoned, delete only the local tag with
`git -C "$qs_repo" tag -d 0.87.0`.

## Step 3 — fail-fast disposable-worktree publication

`publish-module` runs `git subtree split --rejoin`. The disposable worktree confines
its `HEAD` movement; each module starts again at the tagged frozen commit.

```bash
publish_one() (
  set -euo pipefail
  module=$1
  branch_ref="refs/heads/splits/${module}-module"
  parent=$(mktemp -d "/tmp/quickscale-sa117e4-${module}-XXXXXX")
  worktree="$parent/worktree"
  log="$qs_evidence/publish-${module}.log"

  cleanup() {
    primary=$?
    set +e
    test ! -L "$worktree/.venv" || unlink "$worktree/.venv"
    cleanup_rc=0
    test ! -d "$worktree" || git -C "$qs_repo" worktree remove "$worktree" \
      || cleanup_rc=$?
    rmdir "$parent" 2>/dev/null || true
    if test "$primary" -ne 0; then exit "$primary"; fi
    exit "$cleanup_rc"
  }
  trap cleanup EXIT

  row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
  if [[ ! "$row" =~ ^([0-9a-f]{40})[[:space:]]+$branch_ref$ ]]; then
    echo "invalid remote row for $branch_ref: $row" >&2
    exit 1
  fi
  expected_sha=${BASH_REMATCH[1]}

  git -C "$qs_repo" worktree add --detach "$worktree" "$qs_frozen"
  ln -s "$qs_venv" "$worktree/.venv"
  test -z "$(git -C "$worktree" status --porcelain)"
  test "$(git -C "$worktree" rev-parse HEAD)" = "$qs_frozen"
  test "$(git -C "$worktree" rev-list -n 1 "$qs_version")" = "$qs_frozen"
  (
    cd "$worktree"
    make publish-module MODULE="$module" EXPECTED_REMOTE_SHA="$expected_sha"
  ) >"$log" 2>&1

  local_sha=$(git -C "$qs_repo" rev-parse "$branch_ref")
  post_row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
  test "$post_row" = "$local_sha"$'\t'"$branch_ref"
)

for module in "${qs_modules[@]}"; do
  if ! publish_one "$module"; then
    echo "stopped at $module; inspect $qs_evidence/publish-${module}.log" >&2
    exit 1
  fi
done
```

Every rerun obtains fresh remote SHAs. The loop never continues after failure.

### Exact branch and pre-seal table

This function fails if a remote query fails, a branch does not return exactly one SHA,
a remote manifest differs by one byte, its parsed version is not `0.87.0`, or a seal tag
already exists.

```bash
collect_unsealed_table() {
  output=$1
  : >"$output"
  printf 'module\tbranch_sha\tmanifest_version\ttag\n' >>"$output"
  for module in "${qs_modules[@]}"; do
    branch_ref="refs/heads/splits/${module}-module"
    tag_ref="refs/tags/splits/${module}-module/${qs_version}"
    row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
    [[ "$row" =~ ^([0-9a-f]{40})[[:space:]]+$branch_ref$ ]]
    sha=${BASH_REMATCH[1]}
    tag_row=$(git -C "$qs_repo" ls-remote --refs --tags origin "$tag_ref")
    test -z "$tag_row"
    git -C "$qs_repo" fetch --no-tags origin "$branch_ref" >/dev/null
    test "$(git -C "$qs_repo" rev-parse 'FETCH_HEAD^{commit}')" = "$sha"
    remote_manifest="$qs_evidence/${module}.remote.module.yml"
    git -C "$qs_repo" show "$sha:module.yml" >"$remote_manifest"
    cmp "$qs_repo/quickscale_modules/$module/module.yml" "$remote_manifest"
    manifest_version=$("$qs_venv/bin/python" -c \
      'import sys,yaml; print(yaml.safe_load(sys.stdin)["version"])' \
      <"$remote_manifest")
    test "$manifest_version" = "$qs_version"
    printf '%s\t%s\t%s\tabsent\n' \
      "$module" "$sha" "$manifest_version" >>"$output"
  done
  test "$(wc -l <"$output")" -eq 13
}

collect_unsealed_table "$qs_evidence/post-publish.tsv"
cat "$qs_evidence/post-publish.tsv"
```

### Installed all-module branch proof

Provision from a clean detached source, generate the same all-module plan used by the
installed smoke gate, and apply with all twelve explicit branch refs. Answer no at the
late destructive gate. Expected exit 1 plus `Steps 1-10 completed successfully` proves
managed wiring was reached without Docker/database operations.

```bash
verify_parent=$(mktemp -d /tmp/quickscale-sa117e4-verify-XXXXXX)
verify_source="$verify_parent/source"
verify_output="$verify_parent/installed"
git -C "$qs_repo" worktree add --detach "$verify_source" "$qs_frozen"
mkdir "$verify_output"
"$verify_source/scripts/provision_installed_venv.sh" "$verify_source" "$verify_output"
installed_qs="$verify_output/venv/bin/quickscale"
installed_work="$verify_output/work"
(
  cd "$installed_work"
  printf '\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n' \
    | env -u PYTHONPATH -u PYTHONHOME "$installed_qs" plan testproj
)
split_args=()
for module in "${qs_modules[@]}"; do
  split_args+=(--split-ref "$module=splits/${module}-module")
done
set +e
(
  cd "$installed_work/testproj"
  printf 'n\ny\nn\n' | env -u PYTHONPATH -u PYTHONHOME QUICKSCALE_DEBUG=1 \
    "$installed_qs" apply "${split_args[@]}"
) >"$qs_evidence/branch-override-apply.log" 2>&1
branch_apply_rc=$?
set -e
test "$branch_apply_rc" -eq 1
grep -F 'Steps 1-10 completed successfully' "$qs_evidence/branch-override-apply.log"
! grep -F 'KeyError' "$qs_evidence/branch-override-apply.log"
! grep -F 'Traceback (most recent call last)' \
  "$qs_evidence/branch-override-apply.log"
git -C "$qs_repo" worktree remove "$verify_source"
rm -rf "$verify_parent"
```

The final removal targets only the validated `/tmp/quickscale-sa117e4-verify-*` allocation.
On failure, retain it for diagnosis and clean that exact path only after review.

## Step 4 — human-gated immutable seal

Immediately before sealing:

```bash
collect_unsealed_table "$qs_evidence/preseal.tsv"
cat "$qs_evidence/preseal.tsv"
```

**Stop.** A maintainer must freshly confirm all twelve complete SHAs, version `0.87.0`,
byte identity, and proven tag absence. This plan and its review do not grant confirmation.

After confirmation, with `PREVIOUS_VERSION` deliberately omitted:

```bash
seal_parent=$(mktemp -d /tmp/quickscale-sa117e4-seal-XXXXXX)
seal_source="$seal_parent/source"
git -C "$qs_repo" worktree add --detach "$seal_source" "$qs_frozen"
ln -s "$qs_venv" "$seal_source/.venv"
test -z "$(git -C "$seal_source" status --porcelain)"
(
  cd "$seal_source"
  make seal-status VERSION="$qs_version"
  make seal-modules VERSION="$qs_version"
) 2>&1 | tee "$qs_evidence/seal.log"
unlink "$seal_source/.venv"
git -C "$qs_repo" worktree remove "$seal_source"
rmdir "$seal_parent"
```

If sealing stops partway, never move a pushed tag. Diagnose and rerun; an existing tag at
the intended commit is accepted.

## Step 5 — exact refs, manifests, and installed default apply

```bash
: >"$qs_evidence/expected-tags.txt"
for module in "${qs_modules[@]}"; do
  printf 'refs/tags/splits/%s-module/%s\n' "$module" "$qs_version" \
    >>"$qs_evidence/expected-tags.txt"
done
sort -o "$qs_evidence/expected-tags.txt" "$qs_evidence/expected-tags.txt"
git -C "$qs_repo" ls-remote --refs --tags origin 'refs/tags/splits/*' \
  | cut -f2 | sort >"$qs_evidence/actual-tags.txt"
diff -u "$qs_evidence/expected-tags.txt" "$qs_evidence/actual-tags.txt"

for module in "${qs_modules[@]}"; do
  branch_ref="refs/heads/splits/${module}-module"
  tag_ref="refs/tags/splits/${module}-module/${qs_version}"
  branch_row=$(git -C "$qs_repo" ls-remote --refs origin "$branch_ref")
  [[ "$branch_row" =~ ^([0-9a-f]{40})[[:space:]]+$branch_ref$ ]]
  branch_sha=${BASH_REMATCH[1]}
  peeled_row=$(git -C "$qs_repo" ls-remote --tags origin "${tag_ref}^{}")
  test "$peeled_row" = "$branch_sha"$'\t'"${tag_ref}^{}"
  git -C "$qs_repo" fetch --no-tags origin "$branch_ref" >/dev/null
  git -C "$qs_repo" show "$branch_sha:module.yml" \
    >"$qs_evidence/${module}.sealed.module.yml"
  cmp "$qs_repo/quickscale_modules/$module/module.yml" \
    "$qs_evidence/${module}.sealed.module.yml"
done
test -z "$(git -C "$qs_repo" ls-remote --refs --tags origin \
  "refs/tags/$qs_version")"
```

The approved harness hashes must remain:

```text
verify_public_module_apply.py  b1fb28ff15da7159bb35421c26a1a5f9dd53e4561031ae6d244d58b8ece522ac
verify_sa117_publication.py    5fe178d94316e51ad462351a468a657a77735116afdcc4e8ce1f093a40dee5cc
```

Re-review on hash drift. Provision a fresh fixture, generate the same all-module plan, and
invoke the harness with **no `--split-ref` and no other QuickScale CLI override**:

```bash
test "$(sha256sum "$qs_repo/scripts/verify_public_module_apply.py" | cut -d' ' -f1)" \
  = b1fb28ff15da7159bb35421c26a1a5f9dd53e4561031ae6d244d58b8ece522ac
test "$(sha256sum "$qs_repo/scripts/verify_sa117_publication.py" | cut -d' ' -f1)" \
  = 5fe178d94316e51ad462351a468a657a77735116afdcc4e8ce1f093a40dee5cc

final_parent=$(mktemp -d /tmp/quickscale-sa117e4-final-XXXXXX)
final_source="$final_parent/source"
final_output="$final_parent/installed"
git -C "$qs_repo" worktree add --detach "$final_source" "$qs_frozen"
mkdir "$final_output"
"$final_source/scripts/provision_installed_venv.sh" "$final_source" "$final_output"
final_qs="$final_output/venv/bin/quickscale"
final_work="$final_output/work"
(
  cd "$final_work"
  printf '\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n' \
    | env -u PYTHONPATH -u PYTHONHOME "$final_qs" plan testproj
)
env -u PYTHONPATH -u PYTHONHOME "$qs_venv/bin/python" \
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
git -C "$qs_repo" worktree remove "$final_source"
rm -rf "$final_parent"
```

Exit 0 closes `SA117E3-PUBLIC-ANALYTICS-001`. The harness owns exact Compose-project
cleanup. Retain its JSON evidence under `$qs_evidence`. On failure, retain the exact
`/tmp/quickscale-sa117e4-final-*` allocation for diagnosis.

## Selected teams cleanup

Only after step 5 passes, present the fresh SHA for a separate maintainer confirmation:

```bash
teams_ref=refs/heads/splits/teams-module
teams_row=$(git -C "$qs_repo" ls-remote --refs origin "$teams_ref")
[[ "$teams_row" =~ ^([0-9a-f]{40})[[:space:]]+$teams_ref$ ]]
teams_sha=${BASH_REMATCH[1]}
# separate maintainer confirmation of $teams_ref at $teams_sha happens here
git -C "$qs_repo" push \
  --force-with-lease="$teams_ref:$teams_sha" origin ":$teams_ref"
test -z "$(git -C "$qs_repo" ls-remote --refs origin "$teams_ref")"
```

Finally require the exact twelve-name branch set:

```bash
: >"$qs_evidence/expected-heads.txt"
for module in "${qs_modules[@]}"; do
  printf 'refs/heads/splits/%s-module\n' "$module" \
    >>"$qs_evidence/expected-heads.txt"
done
sort -o "$qs_evidence/expected-heads.txt" "$qs_evidence/expected-heads.txt"
git -C "$qs_repo" ls-remote --heads origin 'refs/heads/splits/*' \
  | cut -f2 | sort >"$qs_evidence/actual-heads.txt"
diff -u "$qs_evidence/expected-heads.txt" "$qs_evidence/actual-heads.txt"
```

## Validation and prohibitions

| Command | Expected |
|---|---|
| `poetry run pytest scripts/test_publish_module.py quickscale_core/tests/test_git_utils.py -q --no-cov` | exit 0 |
| `make version-check` | exit 0 |
| `make check QUIET=1` | exit 0 |
| `make quality` | exit 2, SA140 only |

This plan authorizes no core-tag push, `git push --tags`, PyPI action, product-code edit,
or pre-granted human confirmation. Phase 0 closes only when an independent reviewer—not
this revision's author—returns `STATUS: ok` against the frozen source and these plan bytes.
