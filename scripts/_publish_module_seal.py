"""
Seal primitives for the ``publish_module`` facade and its private siblings.

The SA136d check-then-act seal state machine lives here in small phases so no
function crosses the complexity gate; every git collaborator is resolved
through :mod:`_publish_module_git` at call time (decisions.md,
Split-Facade Seams).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import _publish_module_core as _core
import _publish_module_git as _git
from _publish_module_git import GitError, GitRunner, SealError


@dataclass(frozen=True)
class SealOutcome:
    """The immutable result of one module seal attempt."""

    module: str
    version: str
    branch: str
    tag: str
    commit: str
    pushed: bool


# These aliases keep the result/error vocabulary explicit for callers that
# consume the primitive without exposing a CLI or batch dispatch yet.
SealResult = SealOutcome


@dataclass(frozen=True)
class SealBatchOutcome:
    """The cumulative result of a serial seal-all attempt."""

    succeeded: tuple[str, ...]
    failed: str | None
    not_attempted: tuple[str, ...]


def _cleanup_created_tag(
    tag: str,
    *,
    armed: bool,
    runner: GitRunner,
) -> str | None:
    """Discharge the local cleanup obligation without touching any remote ref."""
    if not armed:
        return None
    try:
        _git.delete_local_tag(tag, runner=runner)
    except (GitError, OSError) as exc:
        return str(exc)
    return None


def _select_seal_commit(
    module: str,
    version: str,
    previous_version: str | None,
    branch_sha: str,
    runner: GitRunner,
) -> str:
    """Reuse the previous commit when its tree matches the selected branch tree."""
    seal_commit = branch_sha
    if previous_version is None:
        return seal_commit
    previous_tag = _git.resolve_split_tag(module, previous_version)
    previous_commit = _git.get_local_tag_commit(previous_tag, runner=runner)
    if previous_commit is None:
        raise _git._seal_error(
            f"Previous local tag {previous_tag!r} is absent",
            module=module,
            version=version,
        )
    previous_tree = _git.get_tree_sha(previous_commit, runner=runner)
    branch_tree = _git.get_tree_sha(branch_sha, runner=runner)
    if previous_tree == branch_tree:
        seal_commit = previous_commit
    return seal_commit


def _check_local_tag(
    tag: str,
    seal_commit: str,
    module: str,
    version: str,
    runner: GitRunner,
) -> bool:
    """Return True when the local tag is absent, arming the cleanup obligation."""
    local_tag = _git.get_local_tag_commit(tag, runner=runner)
    if local_tag is None:
        return True
    local_tag_sha = _git._seal_sha(
        local_tag,
        description=f"local tag {tag!r}",
        module=module,
        version=version,
    )
    if local_tag_sha != seal_commit:
        raise _git._seal_error(
            f"Local tag {tag!r} conflicts: {local_tag_sha} != {seal_commit}",
            module=module,
            version=version,
        )
    return False


def _existing_remote_tag_outcome(
    module: str,
    version: str,
    branch: str,
    branch_sha: str,
    tag: str,
    seal_commit: str,
    runner: GitRunner,
) -> SealOutcome | None:
    """Return the verified no-mutation outcome when the remote tag already exists."""
    remote_tag = _git.resolve_remote_ref("origin", tag, runner=runner)
    if not remote_tag:
        return None
    remote_tag_sha = _git._seal_sha(
        remote_tag,
        description=f"remote tag {tag!r}",
        module=module,
        version=version,
    )
    if remote_tag_sha != seal_commit:
        raise _git._seal_error(
            f"Remote tag {tag!r} conflicts: {remote_tag_sha} != {seal_commit}",
            module=module,
            version=version,
        )
    post_branch = _git._seal_sha(
        _git.resolve_remote_ref("origin", branch, runner=runner),
        description=f"post-action remote branch {branch!r}",
        module=module,
        version=version,
    )
    if post_branch != branch_sha:
        raise _git._seal_error(
            f"Remote branch {branch!r} moved after seal verification",
            module=module,
            version=version,
        )
    return SealOutcome(module, version, branch, tag, seal_commit, pushed=False)


@dataclass
class _SealAttemptState:
    """Mutable context the push-failure probe reports back to the composer."""

    probe_context: str | None = None


def _probe_remote_tag(
    module: str,
    version: str,
    tag: str,
    seal_commit: str,
    runner: GitRunner,
) -> str | None:
    """Describe what the remote tag holds after a failed push, if readable."""
    try:
        remote_after_failure = _git.resolve_remote_ref("origin", tag, runner=runner)
        if not remote_after_failure:
            return None
        remote_after_failure_sha = _git._seal_sha(
            remote_after_failure,
            description=f"remote tag probe {tag!r}",
            module=module,
            version=version,
        )
        if remote_after_failure_sha != seal_commit:
            return (
                f"remote tag probe found conflicting commit "
                f"{remote_after_failure_sha} != {seal_commit}"
            )
        return None
    except (GitError, OSError) as probe_error:
        return f"remote tag probe failed: {probe_error}"


def _push_and_probe(
    module: str,
    version: str,
    tag: str,
    seal_commit: str,
    state: _SealAttemptState,
    runner: GitRunner,
) -> None:
    """Push exactly one tag ref and record probe context when the push fails."""
    try:
        _git.push_tag(
            tag,
            remote="origin",
            refspec=f"{tag}:refs/tags/{tag}",
            runner=runner,
        )
    except (GitError, OSError) as push_error:
        state.probe_context = _probe_remote_tag(module, version, tag, seal_commit, runner)
        raise _git._seal_error(
            f"Tag push failed for {tag!r}: {push_error}",
            module=module,
            version=version,
        ) from push_error


def _verify_post_action(
    module: str,
    version: str,
    branch: str,
    branch_sha: str,
    tag: str,
    seal_commit: str,
    runner: GitRunner,
) -> None:
    """Verify the pushed tag peels to the sealed commit and the branch stayed put."""
    post_tag = _git.resolve_remote_ref("origin", f"{tag}^{{}}", runner=runner)
    if (
        not post_tag
        or _git._seal_sha(
            post_tag,
            description=f"post-action remote tag {tag!r}",
            module=module,
            version=version,
        )
        != seal_commit
    ):
        raise _git._seal_error(
            f"Remote tag {tag!r} failed post-action verification",
            module=module,
            version=version,
        )

    post_branch = _git._seal_sha(
        _git.resolve_remote_ref("origin", branch, runner=runner),
        description=f"post-action remote branch {branch!r}",
        module=module,
        version=version,
    )
    if post_branch != branch_sha:
        raise _git._seal_error(
            f"Remote branch {branch!r} moved after tag push; immutable tag remains",
            module=module,
            version=version,
        )


def _raise_seal_failure(
    error: GitError | OSError,
    *,
    module: str,
    version: str,
    probe_context: str | None,
    cleanup_error: str | None,
    cleanup_was_primary: bool,
) -> None:
    """Compose the operator-facing seal failure with the pre-split precedence."""
    message = str(error)
    if probe_context:
        message = f"{message}; {probe_context}"
    if cleanup_error and not cleanup_was_primary:
        message = f"{message}; local cleanup also failed: {cleanup_error}"
    if isinstance(error, SealError) and probe_context is None and cleanup_error is None:
        raise error
    raise _git._seal_error(
        message,
        module=module,
        version=version,
        cleanup_error=cleanup_error,
    ) from error


def _seal_mutate_and_verify(
    module: str,
    version: str,
    branch: str,
    branch_sha: str,
    tag: str,
    seal_commit: str,
    *,
    cleanup_armed: bool,
    runner: GitRunner,
) -> SealOutcome:
    """Create, push, and verify the seal, discharging cleanup on every exit."""
    state = _SealAttemptState()
    primary_error: GitError | OSError | None = None
    cleanup_error: str | None = None
    cleanup_was_primary = False
    pending_exception: BaseException | None = None
    try:
        if cleanup_armed:
            _git.create_annotated_tag(tag, seal_commit, runner=runner)
        _push_and_probe(module, version, tag, seal_commit, state, runner)
        _verify_post_action(module, version, branch, branch_sha, tag, seal_commit, runner)
        cleanup_armed = False
    except (GitError, OSError) as exc:
        primary_error = exc
    except BaseException as exc:
        pending_exception = exc
    finally:
        cleanup_error = _cleanup_created_tag(tag, armed=cleanup_armed, runner=runner)
        if cleanup_error and primary_error is None:
            primary_error = OSError(cleanup_error)
            cleanup_was_primary = True
        if pending_exception is not None and primary_error is None:
            raise pending_exception

    if primary_error is not None:
        _raise_seal_failure(
            primary_error,
            module=module,
            version=version,
            probe_context=state.probe_context,
            cleanup_error=cleanup_error,
            cleanup_was_primary=cleanup_was_primary,
        )
    return SealOutcome(module, version, branch, tag, seal_commit, pushed=True)


def _seal_module(
    module: str,
    version: str,
    *,
    previous_version: str | None = None,
    runner: GitRunner,
) -> SealOutcome:
    """Seal one split module with strict check-then-act verification."""
    branch = _git.resolve_split_branch(module)
    tag = _git.resolve_split_tag(module, version)
    branch_sha = _git._seal_sha(
        _git.resolve_remote_ref("origin", branch, runner=runner),
        description=f"remote branch {branch!r}",
        module=module,
        version=version,
    )
    seal_commit = _select_seal_commit(module, version, previous_version, branch_sha, runner)

    reread_branch = _git._seal_sha(
        _git.resolve_remote_ref("origin", branch, runner=runner),
        description=f"precondition remote branch {branch!r}",
        module=module,
        version=version,
    )
    if reread_branch != branch_sha:
        raise _git._seal_error(
            f"Remote branch {branch!r} moved before seal mutation",
            module=module,
            version=version,
        )

    existing = _existing_remote_tag_outcome(
        module, version, branch, branch_sha, tag, seal_commit, runner
    )
    if existing is not None:
        return existing

    cleanup_armed = _check_local_tag(tag, seal_commit, module, version, runner)
    return _seal_mutate_and_verify(
        module,
        version,
        branch,
        branch_sha,
        tag,
        seal_commit,
        cleanup_armed=cleanup_armed,
        runner=runner,
    )


def _invoke_seal_module(
    module: str,
    version: str,
    *,
    previous_version: str | None,
    runner: GitRunner,
) -> SealOutcome:
    """Call the seal primitive without adding a meaningless ``None`` kwarg."""
    if previous_version is None:
        parameter = inspect.signature(_seal_module).parameters.get("previous_version")
        if parameter is not None and parameter.default is inspect.Parameter.empty:
            return _seal_module(
                module,
                version,
                previous_version=None,
                runner=runner,
            )
        return _seal_module(module, version, runner=runner)
    return _seal_module(module, version, previous_version=previous_version, runner=runner)


def _print_seal_batch_summary(outcome: SealBatchOutcome) -> None:
    """Print stable cumulative batch categories for operators and tests."""
    succeeded = " ".join(outcome.succeeded) or "none"
    failed = outcome.failed or "none"
    not_attempted = " ".join(outcome.not_attempted) or "none"
    _core._print_info(f"Succeeded: {succeeded}")
    if outcome.failed:
        _core._print_error(f"Failed: {failed}")
    else:
        _core._print_info("Failed: none")
    _core._print_info(f"Not-attempted: {not_attempted}")


def _seal_all(
    version: str,
    *,
    previous_version: str | None = None,
    runner: GitRunner,
    modules: list[str] | tuple[str, ...] | None = None,
) -> SealBatchOutcome:
    """Seal a frozen authoritative module set serially, stopping on failure."""
    frozen_modules = list(_core._list_modules() if modules is None else modules)
    succeeded: list[str] = []

    for index, module in enumerate(frozen_modules):
        _core._print_info(f"Sealing module: {module}")
        try:
            _invoke_seal_module(
                module,
                version,
                previous_version=previous_version,
                runner=runner,
            )
        except (GitError, SystemExit) as exc:
            outcome = SealBatchOutcome(tuple(succeeded), module, tuple(frozen_modules[index + 1 :]))
            _print_seal_batch_summary(outcome)
            if isinstance(exc, SystemExit):
                raise
            raise _git._seal_error(
                f"Seal-all stopped at module {module!r}: {exc}",
                module=module,
                version=version,
            ) from exc
        succeeded.append(module)

    outcome = SealBatchOutcome(tuple(succeeded), None, ())
    _print_seal_batch_summary(outcome)
    return outcome
