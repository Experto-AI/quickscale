"""Direct regressions for publish-module inventory selection."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

import scripts.publish_module as publish_module
from quickscale_core.contracts import module_discovery


def _write_manifests(root: Path, names: list[str]) -> None:
    for name in names:
        module = root / name
        module.mkdir()
        (module / "module.yml").write_text(f"name: {name}\n")


def test_list_modules_uses_authoritative_inventory_and_picks_up_thirteenth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real manifest is picked up while a bare placeholder is excluded."""
    names = [f"module_{index:02d}" for index in range(12)] + ["reports"]
    _write_manifests(tmp_path, names)
    (tmp_path / "teams").mkdir()

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(tmp_path)
        monkeypatch.setattr(module_discovery, "AUTHORITATIVE_MODULE_COUNT", 13)
        assert publish_module._list_modules() == sorted(names)
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_list_modules_rejects_placeholder_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "teams").mkdir()
    (tmp_path / "teams" / "module.yml").write_text("name: teams\n")

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(tmp_path)
        monkeypatch.setattr(module_discovery, "AUTHORITATIVE_MODULE_COUNT", 1)
        with pytest.raises(module_discovery.ImproperlyConfigured, match="placeholder"):
            publish_module._list_modules()
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_list_modules_fails_closed_when_authoritative_contract_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing inventory contract cannot fall back to directory names."""
    (tmp_path / "billing").mkdir()
    (tmp_path / "teams").mkdir()
    monkeypatch.setattr(publish_module, "_REPO_ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, "quickscale_core.contracts.module_discovery", None)

    with pytest.raises(ModuleNotFoundError):
        publish_module._list_modules()


# ---------------------------------------------------------------------------
# F-002: direct single-module selector must require authoritative-inventory
# membership before release-authority checks, origin prompts, subtree split,
# or push.
# ---------------------------------------------------------------------------


def _patch_selector_surroundings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the selector at *tmp_path* and neutralize git bootstrap calls."""
    monkeypatch.setattr(publish_module, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        publish_module, "build_publication_git_runner", lambda git_executable: object()
    )
    monkeypatch.setattr(publish_module, "is_git_repo", lambda path, runner: True)


def _spy_post_guard_path(monkeypatch: pytest.MonkeyPatch, reached: list[str]) -> None:
    """Record any post-guard release/origin/prompt/mutation call that runs."""
    for name in (
        "_check_release_authoritative",
        "validate_publication_origin",
        "_confirm_uncommitted_changes",
        "_maybe_clean_subtree_cache",
        "_publish_module",
    ):
        monkeypatch.setattr(
            publish_module,
            name,
            lambda *args, _name=name, **kwargs: reached.append(_name),
        )


def test_direct_selector_rejects_placeholder_before_prompts_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-002: 'teams' fails closed before any release/prompt/split/push path."""
    base = tmp_path / "quickscale_modules"
    base.mkdir()
    _write_manifests(base, [f"module_{index:02d}" for index in range(12)])
    (base / "teams").mkdir()
    _patch_selector_surroundings(tmp_path, monkeypatch)

    reached: list[str] = []
    _spy_post_guard_path(monkeypatch, reached)

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(base)
        monkeypatch.setattr(
            sys,
            "argv",
            ["publish_module.py", "teams", "--expected-remote-sha", "ABSENT"],
        )
        with pytest.raises(SystemExit) as excinfo:
            publish_module.main()
        assert excinfo.value.code == 1
        assert reached == []
        out = capsys.readouterr().out
        assert "placeholder inventory only" in out
        assert "teams" in out
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_direct_selector_rejects_unapproved_thirteenth_before_prompts_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-002: an unapproved thirteenth real module fails on inventory count drift."""
    base = tmp_path / "quickscale_modules"
    base.mkdir()
    _write_manifests(base, [f"module_{index:02d}" for index in range(12)] + ["reports"])
    _patch_selector_surroundings(tmp_path, monkeypatch)

    reached: list[str] = []
    _spy_post_guard_path(monkeypatch, reached)

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(base)
        monkeypatch.setattr(
            sys,
            "argv",
            ["publish_module.py", "reports", "--expected-remote-sha", "ABSENT"],
        )
        with pytest.raises(SystemExit) as excinfo:
            publish_module.main()
        assert excinfo.value.code == 1
        assert reached == []
        out = capsys.readouterr().out
        assert "count drift" in out
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_direct_selector_preserves_valid_authoritative_module_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: a valid authoritative name proceeds past the guard unchanged."""
    names = [f"module_{index:02d}" for index in range(12)]
    base = tmp_path / "quickscale_modules"
    base.mkdir()
    _write_manifests(base, names)
    _patch_selector_surroundings(tmp_path, monkeypatch)

    reached: list[str] = []
    monkeypatch.setattr(
        publish_module,
        "_check_release_authoritative",
        lambda runner: reached.append("release"),
    )
    monkeypatch.setattr(
        publish_module,
        "validate_publication_origin",
        lambda path, runner: reached.append("origin"),
    )
    monkeypatch.setattr(
        publish_module,
        "_confirm_uncommitted_changes",
        lambda runner: True,
    )
    monkeypatch.setattr(
        publish_module,
        "_maybe_clean_subtree_cache",
        lambda clean: reached.append("clean"),
    )
    monkeypatch.setattr(
        publish_module,
        "_publish_module",
        lambda module_name, **kwargs: reached.append("publish"),
    )

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(base)
        monkeypatch.setattr(
            sys,
            "argv",
            ["publish_module.py", names[0], "--expected-remote-sha", "ABSENT"],
        )
        publish_module.main()
        assert reached == ["release", "origin", "clean", "publish"]
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_require_authoritative_module_rejects_unknown_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-002: a name absent from a healthy inventory hits the generic rejection."""
    authoritative_names = [f"module_{index:02d}" for index in range(12)]
    monkeypatch.setattr(publish_module, "_list_modules", lambda: authoritative_names)

    with pytest.raises(SystemExit) as excinfo:
        publish_module._require_authoritative_module("nonexistent")
    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "not in the authoritative shipped-module inventory" in out
    assert "nonexistent" in out
    for name in authoritative_names:
        assert f"  - {name}" in out


# ---------------------------------------------------------------------------
# SA136d: the seal contract is deliberately tested against a scripted runner.
# These tests must not create refs or contact a remote.  The response ledger
# mirrors the check-then-act queue from the approved plan, so a production
# implementation cannot accidentally replace a reread with a cached value.
# ---------------------------------------------------------------------------


MODULE = "auth"
BRANCH = "splits/auth-module"
VERSION = "0.88.0"
PREVIOUS_VERSION = "0.87.0"
HEAD_SHA = "a" * 40
OTHER_SHA = "b" * 40
PREVIOUS_COMMIT = "c" * 40
TAG = f"{BRANCH}/{VERSION}"
PREVIOUS_TAG = f"{BRANCH}/{PREVIOUS_VERSION}"


@dataclass(frozen=True)
class _GitResponse:
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class _ScriptedGitRunner:
    """CompletedProcess-compatible runner with an explicit call ledger."""

    def __init__(self, responses: list[_GitResponse], *, local_tag: str | None = None) -> None:
        self._responses = iter(responses)
        self.local_tag = local_tag
        self.calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((tuple(args), kwargs))
        try:
            response = next(self._responses)
        except StopIteration:
            local_ref = f"refs/tags/{TAG}"
            if tuple(args[:4]) == ("show-ref", "--verify", "--quiet", local_ref):
                response = _GitResponse(returncode=0 if self.local_tag else 1)
            elif tuple(args[:3]) == (
                "rev-parse",
                "--verify",
                f"{local_ref}^{{commit}}",
            ):
                response = _GitResponse(
                    stdout=self.local_tag or "", returncode=0 if self.local_tag else 1
                )
            else:
                response = _GitResponse()
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=response.returncode,
            stdout=response.stdout,
            stderr=response.stderr,
        )


class _SealLedger:
    """Scripted Git helper responses and mutation/provenance assertions."""

    def __init__(
        self,
        *,
        branch_reads: tuple[str, str, str] = (HEAD_SHA, HEAD_SHA, HEAD_SHA),
        target_tag: str | None = None,
        post_push_tag: str = HEAD_SHA,
        previous_commit: str = PREVIOUS_COMMIT,
        previous_tree: str = "tree-stable",
        head_tree: str = "tree-stable",
        create_error: str | None = None,
        push_error: str | None = None,
        probe_error: str | None = None,
        probe_value: str | None = None,
        cleanup_error: str | None = None,
        local_tag: str | None = None,
    ) -> None:
        self.runner = _ScriptedGitRunner([], local_tag=local_tag)
        self.branch_reads = list(branch_reads)
        self.target_tag = target_tag
        self.local_tag = local_tag
        self.post_push_tag = post_push_tag
        self.previous_commit = previous_commit
        self.previous_tree = previous_tree
        self.head_tree = head_tree
        self.create_error = create_error
        self.push_error = push_error
        self.probe_error = probe_error
        self.probe_value = probe_value
        self.cleanup_error = cleanup_error
        self.push_attempted = False
        self.events: list[tuple[object, ...]] = []

    def resolve_remote_ref(
        self,
        remote: str,
        ref: str,
        path: Path | None = None,
        *,
        runner: object,
    ) -> str:
        assert runner is self.runner
        self.runner.run(["ls-remote", "--heads", remote, ref])
        self.events.append(("remote-ref", remote, ref))
        if ref == BRANCH:
            return self.branch_reads.pop(0)
        if ref == TAG:
            if self.push_attempted:
                if self.probe_error is not None:
                    raise publish_module.GitError(self.probe_error)
                if self.probe_value is not None:
                    return self.probe_value
            return self.target_tag if self.target_tag is not None else ""
        if ref == f"{TAG}^{{}}":
            return self.post_push_tag
        raise AssertionError(f"unexpected remote ref: {ref}")

    def get_local_tag_commit(
        self,
        tag: str,
        path: Path | None = None,
        *,
        runner: object,
    ) -> str | None:
        assert runner is self.runner
        self.events.append(("local-tag", tag))
        if tag == PREVIOUS_TAG:
            return self.previous_commit
        if tag == TAG:
            return self.local_tag
        raise AssertionError(f"unexpected local tag: {tag}")

    def get_tree_sha(
        self,
        commit: str,
        path: Path | None = None,
        *,
        runner: object,
    ) -> str:
        assert runner is self.runner
        self.runner.run(["rev-parse", f"{commit}^{{tree}}"])
        self.events.append(("tree", commit))
        if commit == PREVIOUS_COMMIT:
            return self.previous_tree
        if commit == HEAD_SHA:
            return self.head_tree
        raise AssertionError(f"unexpected tree lookup: {commit}")

    def create_annotated_tag(
        self,
        tag: str,
        commit: str,
        path: Path | None = None,
        *,
        runner: object,
    ) -> None:
        assert runner is self.runner
        self.runner.run(["tag", "--annotate", tag, commit, "--message", tag])
        self.events.append(("create-tag", tag, commit))
        if self.create_error is not None:
            raise publish_module.GitError(self.create_error)

    def push_tag(
        self,
        tag: str,
        remote: str = "origin",
        path: Path | None = None,
        *,
        refspec: str | None = None,
        runner: object,
    ) -> None:
        assert runner is self.runner
        self.runner.run(["push", remote, refspec or f"{tag}:refs/tags/{tag}"])
        self.events.append(("push-tag", remote, tag, refspec))
        self.push_attempted = True
        if self.push_error is not None:
            raise publish_module.GitError(self.push_error)

    def delete_local_tag(
        self,
        tag: str,
        path: Path | None = None,
        *,
        runner: object,
    ) -> None:
        assert runner is self.runner
        self.runner.run(["tag", "--delete", tag])
        self.events.append(("delete-tag", tag))
        if self.cleanup_error is not None:
            raise publish_module.GitError(self.cleanup_error)


def _install_seal_ledger(monkeypatch: pytest.MonkeyPatch, ledger: _SealLedger) -> None:
    """Install every Git seam through the trusted scripted runner."""
    monkeypatch.setattr(
        publish_module,
        "resolve_remote_ref",
        ledger.resolve_remote_ref,
        raising=False,
    )
    monkeypatch.setattr(publish_module, "get_tree_sha", ledger.get_tree_sha, raising=False)
    monkeypatch.setattr(
        publish_module,
        "get_local_tag_commit",
        ledger.get_local_tag_commit,
        raising=False,
    )
    monkeypatch.setattr(
        publish_module,
        "create_annotated_tag",
        ledger.create_annotated_tag,
        raising=False,
    )
    monkeypatch.setattr(publish_module, "push_tag", ledger.push_tag, raising=False)
    monkeypatch.setattr(
        publish_module,
        "delete_local_tag",
        ledger.delete_local_tag,
        raising=False,
    )
    monkeypatch.setattr(publish_module, "resolve_split_branch", lambda name: BRANCH)
    monkeypatch.setattr(
        publish_module,
        "resolve_module_path",
        lambda name: f"quickscale_modules/{name}",
    )


class TestSealLocalTagPrimitives:
    def _assert_call_ledger(
        self,
        runner: _ScriptedGitRunner,
        expected_args: list[tuple[str, ...]],
    ) -> None:
        assert [call[0] for call in runner.calls] == expected_args
        assert all(
            call[1]
            == {
                "cwd": publish_module._REPO_ROOT,
                "capture_output": True,
                "text": True,
            }
            for call in runner.calls
        )

    def test_absent_tag_is_only_returned_for_show_ref_status_one(self) -> None:
        runner = _ScriptedGitRunner([_GitResponse(returncode=1, stdout="unexpected")])

        assert publish_module.get_local_tag_commit(TAG, runner=runner) is None

        self._assert_call_ledger(
            runner,
            [("show-ref", "--verify", "--quiet", f"refs/tags/{TAG}")],
        )

    @pytest.mark.parametrize(
        ("description", "ref_object", "commit"),
        [
            ("lightweight", HEAD_SHA, HEAD_SHA),
            ("annotated", "c" * 40, OTHER_SHA),
        ],
    )
    def test_present_tag_is_peeled_to_commit(
        self,
        description: str,
        ref_object: str,
        commit: str,
    ) -> None:
        del description
        runner = _ScriptedGitRunner(
            [
                _GitResponse(stdout=ref_object),
                _GitResponse(stdout=f"{commit}\n"),
            ]
        )

        assert publish_module.get_local_tag_commit(TAG, runner=runner) == commit

        self._assert_call_ledger(
            runner,
            [
                ("show-ref", "--verify", "--quiet", f"refs/tags/{TAG}"),
                ("rev-parse", "--verify", f"refs/tags/{TAG}^{{commit}}"),
            ],
        )

    @pytest.mark.parametrize(
        "responses",
        [
            [_GitResponse(returncode=2, stderr="show-ref failed")],
            [_GitResponse(), _GitResponse(returncode=1, stderr="rev-parse failed")],
            [_GitResponse(), _GitResponse(returncode=128, stderr="rev-parse failed")],
        ],
    )
    def test_operational_lookup_failures_raise(self, responses: list[_GitResponse]) -> None:
        runner = _ScriptedGitRunner(responses)

        with pytest.raises(publish_module.GitError):
            publish_module.get_local_tag_commit(TAG, runner=runner)

    def test_malformed_peeled_commit_raises(self) -> None:
        runner = _ScriptedGitRunner([_GitResponse(), _GitResponse(stdout="not-a-sha\n")])

        with pytest.raises(publish_module.GitError):
            publish_module.get_local_tag_commit(TAG, runner=runner)

    def test_runner_oserror_fails_closed(self) -> None:
        class _FailingRunner:
            def run(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                raise OSError("git executable unavailable")

        with pytest.raises(publish_module.GitError):
            publish_module.get_local_tag_commit(TAG, runner=_FailingRunner())

    def test_annotated_creation_is_non_interactive_and_not_forced(self) -> None:
        runner = _ScriptedGitRunner([])

        publish_module.create_annotated_tag(TAG, HEAD_SHA, runner=runner)

        self._assert_call_ledger(
            runner,
            [("tag", "--annotate", TAG, HEAD_SHA, "--message", TAG)],
        )
        assert "--force" not in runner.calls[0][0]


class TestSealMechanics:
    def test_success_returns_structured_seal_outcome(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ledger = _SealLedger()
        _install_seal_ledger(monkeypatch, ledger)

        outcome = publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert outcome == publish_module.SealOutcome(
            module=MODULE,
            version=VERSION,
            branch=BRANCH,
            tag=TAG,
            commit=HEAD_SHA,
            pushed=True,
        )

    def test_trusted_runner_propagates_and_reuses_previous_tree_commit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(post_push_tag=PREVIOUS_COMMIT)
        _install_seal_ledger(monkeypatch, ledger)

        outcome = publish_module._seal_module(
            MODULE,
            VERSION,
            previous_version=PREVIOUS_VERSION,
            runner=ledger.runner,
        )

        assert outcome.commit == PREVIOUS_COMMIT
        assert ledger.events == [
            ("remote-ref", "origin", BRANCH),
            ("local-tag", PREVIOUS_TAG),
            ("tree", PREVIOUS_COMMIT),
            ("tree", HEAD_SHA),
            ("remote-ref", "origin", BRANCH),
            ("remote-ref", "origin", TAG),
            ("local-tag", TAG),
            ("create-tag", TAG, PREVIOUS_COMMIT),
            ("push-tag", "origin", TAG, f"{TAG}:refs/tags/{TAG}"),
            ("remote-ref", "origin", f"{TAG}^{{}}"),
            ("remote-ref", "origin", BRANCH),
        ]
        assert ledger.runner.calls
        assert all(call[1].get("shell") is None for call in ledger.runner.calls)

    def test_absent_target_tag_seals_selected_branch_commit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(previous_tree="old-tree", head_tree="new-tree")
        _install_seal_ledger(monkeypatch, ledger)

        publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert ("create-tag", TAG, HEAD_SHA) in ledger.events
        assert sum(event[0] == "push-tag" for event in ledger.events) == 1

    def test_same_target_tag_is_idempotent_and_does_not_mutate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(target_tag=HEAD_SHA)
        _install_seal_ledger(monkeypatch, ledger)

        publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert not any(
            event[0] in {"create-tag", "push-tag", "delete-tag"} for event in ledger.events
        )

    def test_conflicting_target_tag_fails_closed_without_moving_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(target_tag=OTHER_SHA)
        _install_seal_ledger(monkeypatch, ledger)

        try:
            result = publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)
        except publish_module.GitError, SystemExit:
            pass
        else:
            assert result is False
        assert not any(
            event[0] in {"create-tag", "push-tag", "delete-tag"} for event in ledger.events
        )

    def test_branch_move_between_precondition_and_push_is_reported_unsealed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(branch_reads=(HEAD_SHA, HEAD_SHA, OTHER_SHA))
        _install_seal_ledger(monkeypatch, ledger)

        try:
            result = publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)
        except publish_module.GitError, SystemExit:
            pass
        else:
            assert result is False
        assert ("create-tag", TAG, HEAD_SHA) in ledger.events
        assert ("push-tag", "origin", TAG, f"{TAG}:refs/tags/{TAG}") in ledger.events
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_branch_move_at_immediate_precondition_stops_before_mutation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(branch_reads=(HEAD_SHA, OTHER_SHA, OTHER_SHA))
        _install_seal_ledger(monkeypatch, ledger)

        try:
            result = publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)
        except publish_module.GitError, SystemExit:
            pass
        else:
            assert result is False
        assert not any(event[0] in {"create-tag", "push-tag"} for event in ledger.events)

    def test_local_conflicting_tag_fails_closed_without_remote_mutation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(local_tag=OTHER_SHA)
        _install_seal_ledger(monkeypatch, ledger)

        try:
            result = publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)
        except publish_module.GitError, SystemExit:
            pass
        else:
            assert result is False
        assert not any(
            event[0] in {"create-tag", "push-tag", "delete-tag"} for event in ledger.events
        )

    def test_post_push_peeled_tag_mismatch_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(post_push_tag=OTHER_SHA)
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises((publish_module.GitError, SystemExit)):
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)
        assert ("push-tag", "origin", TAG, f"{TAG}:refs/tags/{TAG}") in ledger.events
        assert ("delete-tag", TAG) in ledger.events

    def test_push_failure_cleans_up_local_tag_and_stops(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(push_error="remote rejected tag")
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises((publish_module.GitError, SystemExit)):
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)
        assert ("create-tag", TAG, HEAD_SHA) in ledger.events
        assert ("delete-tag", TAG) in ledger.events

    def test_create_failure_is_primary_and_cleanup_is_attempted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(create_error="local tag creation failed")
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises(publish_module.SealError) as excinfo:
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert "local tag creation failed" in str(excinfo.value)
        assert not any(event[0] == "push-tag" for event in ledger.events)
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_create_failure_keeps_primary_when_cleanup_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(
            create_error="local tag creation failed",
            cleanup_error="local tag deletion failed",
        )
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises(publish_module.SealError) as excinfo:
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert str(excinfo.value).startswith("local tag creation failed")
        assert "local tag creation failed" in str(excinfo.value)
        assert "local cleanup also failed: local tag deletion failed" in str(excinfo.value)
        assert excinfo.value.cleanup_error == "local tag deletion failed"
        assert not any(event[0] == "push-tag" for event in ledger.events)
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_push_failure_keeps_primary_when_remote_probe_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(push_error="remote rejected tag", probe_error="probe unavailable")
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises(publish_module.SealError) as excinfo:
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert "Tag push failed" in str(excinfo.value)
        assert "remote rejected tag" in str(excinfo.value)
        assert "remote tag probe failed: probe unavailable" in str(excinfo.value)
        assert excinfo.value.cleanup_error is None
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_malformed_remote_probe_keeps_primary_and_cleans_up(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(push_error="remote rejected tag", probe_value="ambiguous")
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises(publish_module.SealError) as excinfo:
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert "Tag push failed" in str(excinfo.value)
        assert "remote rejected tag" in str(excinfo.value)
        assert "Malformed remote tag probe" in str(excinfo.value)
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_remote_conflict_after_push_failure_is_secondary_to_primary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(push_error="remote rejected tag", probe_value=OTHER_SHA)
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises(publish_module.SealError) as excinfo:
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert str(excinfo.value).startswith("Tag push failed")
        assert "remote rejected tag" in str(excinfo.value)
        assert "remote tag probe found conflicting commit" in str(excinfo.value)
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_cleanup_failure_is_secondary_to_push_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _SealLedger(
            push_error="remote rejected tag",
            cleanup_error="local tag deletion failed",
        )
        _install_seal_ledger(monkeypatch, ledger)

        with pytest.raises(publish_module.SealError) as excinfo:
            publish_module._seal_module(MODULE, VERSION, runner=ledger.runner)

        assert str(excinfo.value).startswith("Tag push failed")
        assert "remote rejected tag" in str(excinfo.value)
        assert "local cleanup also failed: local tag deletion failed" in str(excinfo.value)
        assert excinfo.value.cleanup_error == "local tag deletion failed"
        assert sum(event[0] == "delete-tag" for event in ledger.events) == 1

    def test_batch_stops_on_first_failure_and_reports_cumulative_proof(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls: list[str] = []

        def fake_seal(
            module: str,
            version: str,
            *,
            previous_version: str | None = None,
            runner: object,
        ) -> None:
            calls.append(module)
            if module == "module_01":
                raise publish_module.GitError("planned failure")

        monkeypatch.setattr(publish_module, "_seal_module", fake_seal, raising=False)
        monkeypatch.setattr(
            publish_module,
            "_list_modules",
            lambda: ["module_00", "module_01", "module_02"],
        )

        with pytest.raises((publish_module.GitError, SystemExit)):
            publish_module._seal_all(VERSION, runner=object())

        assert calls == ["module_00", "module_01"]
        assert "module_00" in capsys.readouterr().out


class TestSealCliAndStatus:
    def test_parser_exposes_seal_modes_and_version_contract(self) -> None:
        parser = publish_module._build_parser()
        args = parser.parse_args(
            [
                MODULE,
                "--seal",
                "--version",
                VERSION,
                "--previous-version",
                PREVIOUS_VERSION,
            ]
        )
        assert args.seal is True
        assert args.version == VERSION
        assert args.previous_version == PREVIOUS_VERSION

    def test_seal_cli_checks_release_authority_before_mutation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "quickscale_modules").mkdir()
        runner = object()
        calls: list[str] = []
        monkeypatch.setattr(publish_module, "_REPO_ROOT", tmp_path)
        monkeypatch.setattr(
            publish_module, "build_publication_git_runner", lambda executable: runner
        )
        monkeypatch.setattr(publish_module, "is_git_repo", lambda path, runner: True)
        monkeypatch.setattr(
            publish_module,
            "_check_release_authoritative",
            lambda active_runner: (_ for _ in ()).throw(
                publish_module.GitError("not authoritative")
            ),
        )
        monkeypatch.setattr(
            publish_module,
            "_seal_module",
            lambda *args, **kwargs: calls.append("seal"),
            raising=False,
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "publish_module.py",
                MODULE,
                "--seal",
                "--version",
                VERSION,
            ],
        )

        with pytest.raises(SystemExit) as excinfo:
            publish_module.main()
        assert excinfo.value.code == 1
        assert calls == []

    def test_status_emits_twelve_sealed_version_rows(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        names = [f"module_{index:02d}" for index in range(12)]
        monkeypatch.setattr(publish_module, "_list_modules", lambda: names)
        monkeypatch.setattr(publish_module, "_warn_uncommitted_changes", lambda runner: None)
        monkeypatch.setattr(
            publish_module,
            "_show_provenance_diagnostics",
            lambda runner: True,
        )
        monkeypatch.setattr(
            publish_module,
            "_get_module_publish_state",
            lambda module, runner: ("up-to-date", HEAD_SHA, HEAD_SHA, "remote-tracking"),
        )
        monkeypatch.setattr(
            publish_module,
            "resolve_remote_ref",
            lambda remote, ref, *, runner: HEAD_SHA,
        )

        publish_module._show_status(object(), version=VERSION)
        output = capsys.readouterr().out
        assert f"sealed@{VERSION}" in output
        assert all(name in output for name in names)

    def test_seal_all_stops_without_calling_later_modules(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(
            publish_module,
            "_list_modules",
            lambda: ["module_00", "module_01", "module_02"],
        )

        def fake_seal(
            module: str,
            version: str,
            *,
            previous_version: str | None,
            runner: object,
        ) -> None:
            calls.append(module)
            if module == "module_01":
                raise publish_module.GitError("stop")

        monkeypatch.setattr(publish_module, "_seal_module", fake_seal, raising=False)
        with pytest.raises((publish_module.GitError, SystemExit)):
            publish_module._seal_all(VERSION, runner=object())
        assert calls == ["module_00", "module_01"]


class TestSealMakeInterfaces:
    def test_makefile_has_guarded_seal_targets_and_explicit_single_dispatch(
        self,
    ) -> None:
        makefile = Path(__file__).resolve().parents[1] / "Makefile"
        text = makefile.read_text()
        for target in ("seal-module:", "seal-modules:", "seal-status:"):
            assert target in text
        assert "EXPECTED_REMOTE_SHA" in text
        assert "scripts/publish_module.sh" in text
        assert "--seal" in text
        assert "--seal-all" in text
        assert "--status" in text
        assert "git push --tags" in text
        assert "PyPI" in text

    def test_make_seal_module_requires_module_and_version(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
        assert "seal-module:" in text, "planned seal-module target is absent"
        assert "seal-modules:" in text, "planned seal-modules target is absent"
        block = text[text.index("seal-module:") : text.index("seal-modules:")]
        assert 'if [ -z "$(MODULE)" ]' in block
        assert "$(origin VERSION)" in block
        assert '[ -z "$(VERSION)" ]' in block
        assert "--seal" in block
        assert "--version $(VERSION)" in block
        assert "--previous-version $(PREVIOUS_VERSION)" in block

    def test_make_seal_all_and_status_require_version(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
        assert "seal-modules:" in text, "planned seal-modules target is absent"
        assert "seal-status:" in text, "planned seal-status target is absent"
        all_block = text[text.index("seal-modules:") : text.index("seal-status:")]
        status_block = text[text.index("seal-status:") :]
        assert "$(origin VERSION)" in all_block
        assert "$(origin VERSION)" in status_block
        assert "--seal-all" in all_block
        assert "--status" in status_block
        assert "$(VERSION)" in all_block
        assert "$(VERSION)" in status_block
