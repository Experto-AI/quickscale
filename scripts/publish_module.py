#!/usr/bin/env python3
r"""
Provenance-aware split-publish wrapper for QuickScale modules (F2.8, F2.9a, F2.9b).

This script replaces the hardcoded module-path and branch-resolution logic
that previously lived entirely in ``scripts/publish_module.sh``.  It uses
the provenance-aware helper surface from
``quickscale_core.utils.git_utils`` so the split/publish execution path
shares the same resolution conventions as the embed/update paths.

F2.9a adds a release-authoritative gate: mutating publish flows refuse to
run unless the source state is release-authoritative (VERSION file matches
a git tag pointing at HEAD), aligned with the publish workflow authority in
.github/workflows/publish.yml.  The --status flag remains read-only and
does not require release-authoritative state.

F2.9b adds operator-facing diagnostics: --status reports release provenance
(tagged/untagged/mismatched source state), per-module split-branch state with
local-vs-published SHAs, and explicit next-action guidance.  --status stays
read-only and never fails closed; the mutating flows continue to fail closed
with the same explicit next-action guidance.

    Usage:
        poetry run python scripts/publish_module.py \\
            <module_name> --expected-remote-sha <sha|ABSENT> [--clean]
        poetry run python scripts/publish_module.py --seal <module_name> \
            --version <version> [--previous-version <version>]
        poetry run python scripts/publish_module.py --seal-all \
            --version <version> [--previous-version <version>]
        poetry run python scripts/publish_module.py --status [--version <version>]
        poetry run python scripts/publish_module.py --publish-outdated [--clean]

    Phase 4 (SA117): All mutating single-module publish calls require
    ``--expected-remote-sha``.  The value must be a 40-character hex SHA
    or the literal ``ABSENT``.  ``--status`` rejects the flag; the disabled
    ``--publish-outdated`` action accepts it only long enough to emit its
    Phase 4 safety guidance.

    Phase 4 also disables ``--publish-outdated`` entirely: it used bare
    ``--force`` internally, which violates the force-with-lease safety
    contract.  Use single-module publish with per-module
    ``--expected-remote-sha`` instead.
"""

from __future__ import annotations

import argparse
import inspect
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure the quickscale_core package is importable when running from the
# repository root via ``poetry run python scripts/publish_module.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORE_SRC = _REPO_ROOT / "quickscale_core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

from quickscale_core.utils.git_utils import (  # noqa: E402
    GitError,
    GitRunner,
    build_publication_git_runner,
    is_git_repo,
    is_release_authoritative,
    is_working_directory_clean,
    push_split_branch,
    resolve_module_path,
    resolve_split_branch,
    resolve_split_tag,
    run_git_subtree_split,
    validate_expected_sha,
    validate_module_name,
    validate_publication_origin,
    validate_tag_name,
)

# ---------------------------------------------------------------------------
# Output helpers (match the bash script's color conventions)
# ---------------------------------------------------------------------------

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def _print_info(msg: str) -> None:
    print(f"{BLUE}ℹ️  {msg}{NC}")


def _print_success(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{NC}")


def _print_warning(msg: str) -> None:
    print(f"{YELLOW}⚠️  {msg}{NC}")


def _print_error(msg: str) -> None:
    print(f"{RED}❌ {msg}{NC}")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _list_modules() -> list[str]:
    """Return the fail-hard authoritative shipped-module inventory."""
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        authoritative_module_names,
    )

    return authoritative_module_names()


def _require_authoritative_module(module_name: str) -> None:
    """
    Fail closed unless *module_name* is in the authoritative shipped-module inventory.

    This is the direct single-module selector guard (F-002): it consults
    :func:`_list_modules` (backed by ``authoritative_module_names()``)
    before any release-authority check, origin prompt, subtree split, or
    push.  A placeholder name (``teams``) and an unapproved inventory
    addition (count drift) therefore fail before any outward or mutating
    path, instead of relying on on-disk directory existence alone.
    """
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        ImproperlyConfigured,
        get_placeholder_rejection_reason,
    )

    try:
        authoritative_names = _list_modules()
    except ImproperlyConfigured as exc:
        _print_error(f"Authoritative module inventory unavailable: {exc}")
        sys.exit(1)

    if module_name not in authoritative_names:
        placeholder_reason = get_placeholder_rejection_reason(module_name)
        if placeholder_reason is not None:
            _print_error(placeholder_reason)
        else:
            _print_error(
                f"Module '{module_name}' is not in the authoritative shipped-module inventory."
            )
        print()
        _print_info("Available modules:")
        for name in authoritative_names:
            print(f"  - {name}")
        sys.exit(1)


def _has_uncommitted_changes(runner: GitRunner) -> bool:
    """Return True if the working directory has uncommitted changes."""
    try:
        # Publication uses git_utils' binary, NUL-safe status parser.  Any
        # malformed non-empty stream is treated as dirty/fail-closed rather
        # than being silently normalized by text or newline parsing.
        return not is_working_directory_clean(_REPO_ROOT, runner=runner)
    except GitError:
        return True


def _warn_uncommitted_changes(runner: GitRunner) -> None:
    if _has_uncommitted_changes(runner):
        _print_warning(
            "You have uncommitted changes. "
            "Split status and published branches only include committed history."
        )


def _confirm_uncommitted_changes(runner: GitRunner) -> bool:
    """
    Prompt the user when uncommitted changes are present.

    Returns True if the user wants to continue, False to abort.
    """
    if not _has_uncommitted_changes(runner):
        return True
    _print_warning(
        "You have uncommitted changes. Published split branches only include committed history."
    )
    print()
    reply = input("Continue anyway? (y/N): ")
    if reply.strip().lower() not in ("y", "yes"):
        _print_info("Aborted by user")
        return False
    return True


def _maybe_clean_subtree_cache(clean: bool) -> None:
    if clean:
        _print_info("Cleaning git subtree cache...")
        cache_dir = _REPO_ROOT / ".git" / "subtree-cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


# ---------------------------------------------------------------------------
# SA136d seal primitive
# ---------------------------------------------------------------------------


_SEAL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class SealOutcome:
    """The immutable result of one module seal attempt."""

    module: str
    version: str
    branch: str
    tag: str
    commit: str
    pushed: bool


class SealError(GitError):
    """A fail-closed seal error with machine-readable operation context."""

    def __init__(
        self,
        message: str,
        *,
        module: str,
        version: str,
        cleanup_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.module = module
        self.version = version
        self.cleanup_error = cleanup_error


# These aliases keep the result/error vocabulary explicit for callers that
# consume the primitive without exposing a CLI or batch dispatch yet.
SealResult = SealOutcome


@dataclass(frozen=True)
class SealBatchOutcome:
    """The cumulative result of a serial seal-all attempt."""

    succeeded: tuple[str, ...]
    failed: str | None
    not_attempted: tuple[str, ...]


def _seal_error(
    message: str,
    *,
    module: str,
    version: str,
    cleanup_error: str | None = None,
) -> SealError:
    return SealError(
        message,
        module=module,
        version=version,
        cleanup_error=cleanup_error,
    )


def _seal_sha(value: object, *, description: str, module: str, version: str) -> str:
    """Return a canonical SHA or reject ambiguous Git output."""
    if not isinstance(value, str):
        raise _seal_error(
            f"Malformed {description}: expected a 40-hex SHA",
            module=module,
            version=version,
        )
    sha = value.strip()
    if not _SEAL_SHA_RE.fullmatch(sha):
        raise _seal_error(
            f"Malformed {description}: expected one 40-hex SHA, got {value!r}",
            module=module,
            version=version,
        )
    return sha.lower()


def _parse_remote_records(
    output: object,
    *,
    expected_refs: set[str],
    description: str,
    module: str,
    version: str,
) -> dict[str, str]:
    """Parse one strict ``ls-remote`` response without accepting ambiguity."""
    if not isinstance(output, str):
        raise _seal_error(
            f"Malformed {description}: expected text output",
            module=module,
            version=version,
        )
    records = output.splitlines()
    if any(not record.strip() for record in records):
        raise _seal_error(
            f"Malformed {description}: blank record",
            module=module,
            version=version,
        )
    parsed: dict[str, str] = {}
    for record in records:
        fields = record.split()
        if len(fields) != 2:
            raise _seal_error(
                f"Malformed {description}: expected SHA and ref, got {record!r}",
                module=module,
                version=version,
            )
        sha, ref = fields
        if ref not in expected_refs:
            raise _seal_error(
                f"Unexpected ref in {description}: {ref!r}",
                module=module,
                version=version,
            )
        if ref in parsed:
            raise _seal_error(
                f"Duplicate ref in {description}: {ref!r}",
                module=module,
                version=version,
            )
        parsed[ref] = _seal_sha(
            sha,
            description=f"{description} SHA",
            module=module,
            version=version,
        )
    return parsed


def resolve_remote_ref(
    remote: str,
    ref: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> str:
    """
    Resolve a branch or split tag using the trusted publication runner.

    A tag lookup reads its direct and peeled records together.  A peeled
    lookup (used for post-action verification) reads only the peeled record.
    The empty string is reserved for an absent tag; branches are required.
    """
    module = "seal"
    version = "unknown"
    # The wrapper is also a test seam.  The seal itself supplies the precise
    # module/version context when validating the returned value.
    cwd = path or _REPO_ROOT
    if ref.endswith("^{}"):
        tag = ref[:-3]
        validate_tag_name(tag)
        args = ["ls-remote", "--tags", "--", remote, f"refs/tags/{tag}^{{}}"]
        result = runner.run(args, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GitError(f"Failed to resolve remote tag {tag!r}: {result.stderr}")
        parsed = _parse_remote_records(
            result.stdout,
            expected_refs={f"refs/tags/{tag}^{{}}"},
            description=f"peeled remote tag {tag!r}",
            module=module,
            version=version,
        )
        return next(iter(parsed.values()), "")

    if ref.startswith("splits/") and ref.count("/") == 1:
        args = ["ls-remote", "--heads", remote, ref]
        result = runner.run(args, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GitError(f"Failed to resolve remote branch {ref!r}: {result.stderr}")
        parsed = _parse_remote_records(
            result.stdout,
            expected_refs={f"refs/heads/{ref}"},
            description=f"remote branch {ref!r}",
            module=module,
            version=version,
        )
        if not parsed:
            raise GitError(f"Remote branch {ref!r} is absent")
        return next(iter(parsed.values()))

    validate_tag_name(ref)
    direct_ref = f"refs/tags/{ref}"
    peeled_ref = f"{direct_ref}^{{}}"
    args = ["ls-remote", "--tags", "--", remote, direct_ref, peeled_ref]
    result = runner.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(f"Failed to resolve remote tag {ref!r}: {result.stderr}")
    parsed = _parse_remote_records(
        result.stdout,
        expected_refs={direct_ref, peeled_ref},
        description=f"remote tag {ref!r}",
        module=module,
        version=version,
    )
    return parsed.get(peeled_ref) or parsed.get(direct_ref, "")


def get_tree_sha(
    commit: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> str:
    """Resolve a commit's verified tree through the trusted runner."""
    result = runner.run(
        ["rev-parse", f"{commit}^{{tree}}"],
        cwd=path or _REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to resolve tree for {commit}: {result.stderr}")
    return _seal_sha(
        result.stdout,
        description=f"tree for {commit}",
        module="seal",
        version="unknown",
    )


def get_local_tag_commit(
    tag: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> str | None:
    """Return a local tag's peeled commit SHA, or ``None`` when absent."""
    validate_tag_name(tag)

    cwd = path or _REPO_ROOT
    presence_ref = f"refs/tags/{tag}"
    try:
        presence = runner.run(
            ["show-ref", "--verify", "--quiet", presence_ref],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to inspect local tag {tag!r}: {exc}") from exc

    if presence.returncode == 1:
        return None

    if presence.returncode != 0:
        raise GitError(f"Failed to inspect local tag {tag!r}: {presence.stderr}")

    peeled_ref = f"{presence_ref}^{{commit}}"
    try:
        result = runner.run(
            ["rev-parse", "--verify", peeled_ref],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to resolve local tag {tag!r}: {exc}") from exc
    if result.returncode != 0:
        raise GitError(f"Failed to resolve local tag {tag!r}: {result.stderr}")
    return _seal_sha(
        result.stdout,
        description=f"local tag commit {tag!r}",
        module="seal",
        version="unknown",
    )


def create_annotated_tag(
    tag: str,
    commit: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> None:
    """Create one annotated local tag without force or replacement flags."""
    validate_tag_name(tag)
    result = runner.run(
        ["tag", "--annotate", tag, commit, "--message", tag],
        cwd=path or _REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to create local tag {tag!r}: {result.stderr}")


def push_tag(
    tag: str,
    remote: str = "origin",
    path: Path | None = None,
    *,
    refspec: str | None = None,
    runner: GitRunner,
) -> None:
    """Push exactly one tag ref through the trusted runner."""
    validate_tag_name(tag)
    expected_refspec = f"{tag}:refs/tags/{tag}"
    if refspec is not None and refspec != expected_refspec:
        raise GitError(f"Unexpected tag refspec: {refspec!r}")
    result = runner.run(
        ["push", "--", remote, f"refs/tags/{tag}:refs/tags/{tag}"],
        cwd=path or _REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to push tag {tag!r}: {result.stderr}")


def delete_local_tag(
    tag: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> None:
    """Delete only the local tag named by the seal cleanup obligation."""
    validate_tag_name(tag)
    result = runner.run(
        ["tag", "--delete", tag],
        cwd=path or _REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to delete local tag {tag!r}: {result.stderr}")


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
        delete_local_tag(tag, runner=runner)
    except GitError as exc:
        return str(exc)
    return None


def _seal_module(
    module: str,
    version: str,
    *,
    previous_version: str | None = None,
    runner: GitRunner,
) -> SealOutcome:
    """Seal one split module with strict check-then-act verification."""
    branch = resolve_split_branch(module)
    tag = resolve_split_tag(module, version)
    branch_sha = _seal_sha(
        resolve_remote_ref("origin", branch, runner=runner),
        description=f"remote branch {branch!r}",
        module=module,
        version=version,
    )
    seal_commit = branch_sha

    if previous_version is not None:
        previous_tag = resolve_split_tag(module, previous_version)
        previous_commit = get_local_tag_commit(previous_tag, runner=runner)
        if previous_commit is None:
            raise _seal_error(
                f"Previous local tag {previous_tag!r} is absent",
                module=module,
                version=version,
            )
        previous_tree = get_tree_sha(
            previous_commit,
            runner=runner,
        )
        branch_tree = get_tree_sha(branch_sha, runner=runner)
        if previous_tree == branch_tree:
            seal_commit = previous_commit

    reread_branch = _seal_sha(
        resolve_remote_ref("origin", branch, runner=runner),
        description=f"precondition remote branch {branch!r}",
        module=module,
        version=version,
    )
    if reread_branch != branch_sha:
        raise _seal_error(
            f"Remote branch {branch!r} moved before seal mutation",
            module=module,
            version=version,
        )

    remote_tag = resolve_remote_ref("origin", tag, runner=runner)
    if remote_tag:
        remote_tag_sha = _seal_sha(
            remote_tag,
            description=f"remote tag {tag!r}",
            module=module,
            version=version,
        )
        if remote_tag_sha != seal_commit:
            raise _seal_error(
                f"Remote tag {tag!r} conflicts: {remote_tag_sha} != {seal_commit}",
                module=module,
                version=version,
            )
        post_tag = _seal_sha(
            resolve_remote_ref("origin", f"{tag}^{{}}", runner=runner),
            description=f"post-action remote tag {tag!r}",
            module=module,
            version=version,
        )
        post_branch = _seal_sha(
            resolve_remote_ref("origin", branch, runner=runner),
            description=f"post-action remote branch {branch!r}",
            module=module,
            version=version,
        )
        if post_tag != seal_commit:
            raise _seal_error(
                f"Remote tag {tag!r} failed post-action verification",
                module=module,
                version=version,
            )
        if post_branch != branch_sha:
            raise _seal_error(
                f"Remote branch {branch!r} moved after seal verification",
                module=module,
                version=version,
            )
        return SealOutcome(module, version, branch, tag, seal_commit, pushed=False)

    local_tag = get_local_tag_commit(tag, runner=runner)
    if local_tag is not None:
        local_tag_sha = _seal_sha(
            local_tag,
            description=f"local tag {tag!r}",
            module=module,
            version=version,
        )
        if local_tag_sha != seal_commit:
            raise _seal_error(
                f"Local tag {tag!r} conflicts: {local_tag_sha} != {seal_commit}",
                module=module,
                version=version,
            )

    cleanup_armed = local_tag is None
    probe_context: str | None = None
    try:
        if cleanup_armed:
            create_annotated_tag(tag, seal_commit, runner=runner)

        try:
            push_tag(
                tag,
                remote="origin",
                refspec=f"{tag}:refs/tags/{tag}",
                runner=runner,
            )
        except GitError as push_error:
            try:
                remote_after_failure = resolve_remote_ref("origin", tag, runner=runner)
                if remote_after_failure:
                    remote_after_failure_sha = _seal_sha(
                        remote_after_failure,
                        description=f"remote tag probe {tag!r}",
                        module=module,
                        version=version,
                    )
                    if remote_after_failure_sha != seal_commit:
                        probe_context = (
                            f"remote tag probe found conflicting commit "
                            f"{remote_after_failure_sha} != {seal_commit}"
                        )
            except GitError as probe_error:
                probe_context = f"remote tag probe failed: {probe_error}"
            raise _seal_error(
                f"Tag push failed for {tag!r}: {push_error}",
                module=module,
                version=version,
            ) from push_error

        post_tag = resolve_remote_ref("origin", f"{tag}^{{}}", runner=runner)
        if (
            not post_tag
            or _seal_sha(
                post_tag,
                description=f"post-action remote tag {tag!r}",
                module=module,
                version=version,
            )
            != seal_commit
        ):
            raise _seal_error(
                f"Remote tag {tag!r} failed post-action verification",
                module=module,
                version=version,
            )

        post_branch = _seal_sha(
            resolve_remote_ref("origin", branch, runner=runner),
            description=f"post-action remote branch {branch!r}",
            module=module,
            version=version,
        )
        if post_branch != branch_sha:
            raise _seal_error(
                f"Remote branch {branch!r} moved after tag push; immutable tag remains",
                module=module,
                version=version,
            )
    except GitError as exc:
        cleanup_error = _cleanup_created_tag(
            tag,
            armed=cleanup_armed,
            runner=runner,
        )
        message = str(exc)
        if probe_context:
            message = f"{message}; {probe_context}"
        if cleanup_error:
            message = f"{message}; local cleanup also failed: {cleanup_error}"
        if isinstance(exc, SealError) and probe_context is None and cleanup_error is None:
            raise
        raise _seal_error(
            message,
            module=module,
            version=version,
            cleanup_error=cleanup_error,
        ) from exc

    cleanup_armed = False
    return SealOutcome(module, version, branch, tag, seal_commit, pushed=True)


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
    _print_info(f"Succeeded: {succeeded}")
    _print_error(f"Failed: {failed}") if outcome.failed else _print_info("Failed: none")
    _print_info(f"Not-attempted: {not_attempted}")


def _seal_all(
    version: str,
    *,
    previous_version: str | None = None,
    runner: GitRunner,
    modules: list[str] | tuple[str, ...] | None = None,
) -> SealBatchOutcome:
    """Seal a frozen authoritative module set serially, stopping on failure."""
    frozen_modules = list(_list_modules() if modules is None else modules)
    succeeded: list[str] = []

    for index, module in enumerate(frozen_modules):
        _print_info(f"Sealing module: {module}")
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
            raise _seal_error(
                f"Seal-all stopped at module {module!r}: {exc}",
                module=module,
                version=version,
            ) from exc
        succeeded.append(module)

    outcome = SealBatchOutcome(tuple(succeeded), None, ())
    _print_seal_batch_summary(outcome)
    return outcome


def _check_release_authoritative(runner: GitRunner) -> None:
    """
    Gate: refuse mutating publish flows unless source is release-authoritative (F2.9a).

    Release-authoritative means the VERSION file matches a git tag pointing at
    HEAD, aligned with the publish workflow authority in
    .github/workflows/publish.yml.

    Raises SystemExit with a clear operator-facing message when the source is
    not release-authoritative.  This gate applies to mutating flows only
    (single-module publish); --status remains read-only
    and must not fail closed just because HEAD is untagged.
    (--publish-outdated was disabled in SA117 Phase 4.)
    """
    is_auth, version, tag, reason = is_release_authoritative(_REPO_ROOT, runner=runner)
    if is_auth:
        _print_success(f"Source is release-authoritative (VERSION={version}, tag={tag})")
        return

    _print_error("Source is not release-authoritative (F2.9a gate)")
    if reason:
        _print_error(f"  Reason: {reason}")
    _print_info(
        "Mutating publish flows require the source state to match the publish workflow authority:"
    )
    _print_info("  - VERSION file must contain the release version")
    _print_info("  - HEAD must be tagged with that version")
    _print_info("  - The tag must match the VERSION file content")
    _print_info("See .github/workflows/publish.yml for the authority chain.")
    _print_info(
        "Use --status for read-only inspection (does not require release-authoritative state)."
    )
    sys.exit(1)


def _get_local_split_sha(module_path: str, runner: GitRunner) -> str | None:
    """Compute the subtree split SHA for *module_path* without creating a branch."""
    result = runner.run(
        ["subtree", "split", f"--prefix={module_path}", "--ignore-joins"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return sha if sha else None


def _get_published_split_ref(split_branch: str, runner: GitRunner) -> tuple[str, str]:
    """
    Return ``(sha, source)`` for the published split branch.

    *source* is one of ``local-branch``, ``remote-tracking``, or ``none``.
    """
    # Check local branch first
    result = runner.run(
        ["rev-parse", "--verify", split_branch],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha, "local-branch"

    # Check remote-tracking branch
    result = runner.run(
        ["rev-parse", "--verify", f"origin/{split_branch}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha, "remote-tracking"

    return "", "none"


def _get_module_publish_state(
    module_name: str,
    runner: GitRunner,
) -> tuple[str, str, str, str]:
    """Return ``(state, local_sha, published_sha, published_source)``."""
    try:
        module_path = resolve_module_path(module_name)
        split_branch = resolve_split_branch(module_name)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    local_sha = _get_local_split_sha(module_path, runner)
    if local_sha is None:
        _print_error(f"Could not compute subtree split for module '{module_name}'")
        sys.exit(1)

    published_sha, published_source = _get_published_split_ref(split_branch, runner)

    if not published_sha:
        return "unpublished", local_sha, "", published_source
    if local_sha == published_sha:
        return "up-to-date", local_sha, published_sha, published_source
    return "outdated", local_sha, published_sha, published_source


def _read_repository_version() -> str:
    """Read the repository VERSION value used by implicit status."""
    try:
        version = (_REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GitError(f"Could not read repository VERSION: {exc}") from exc
    if not version:
        raise GitError("Repository VERSION is empty")
    return version


def _get_module_seal_state(
    module_name: str,
    version: str,
    published_sha: str,
    runner: GitRunner,
) -> str:
    """Determine seal state from the peeled remote tag target, read-only."""
    try:
        tag = resolve_split_tag(module_name, version)
        peeled_sha = resolve_remote_ref("origin", f"{tag}^{{}}", runner=runner)
    except GitError, ModuleNotFoundError:
        # Status is diagnostic rather than a gate.  A runner that cannot resolve
        # a remote target is represented as unsealed instead of causing a
        # mutation or turning inspection into a release-authority failure.  The
        # minimal hermetic publication fixture also omits the manifest package
        # used by the shared version parser; that is the same unsealed state for
        # this read-only diagnostic.
        return "unsealed"
    if not peeled_sha:
        return "unsealed"
    try:
        normalized_peeled = _seal_sha(
            peeled_sha,
            description=f"peeled remote tag {tag!r}",
            module=module_name,
            version=version,
        )
    except SealError:
        return "unsealed"
    if published_sha and normalized_peeled == published_sha.lower():
        return f"sealed@{version}"
    return "sealed-conflict"


def _publish_module(
    module_name: str,
    *,
    expected_remote_sha: str,
    runner: GitRunner,
) -> None:
    """
    Split and push a single module using the provenance-aware helpers.

    *expected_remote_sha* is required (SA117 Phase 4): a 40-character hex
    SHA for force-with-lease pinning, or ``ABSENT`` for first-time publish
    (no known remote SHA).  The legacy bare ``--force`` fallback has been
    removed.
    """
    # Defense-in-depth: validate name shape before any path/branch resolution
    # so callers that bypass main() still get a clean GitError, not a
    # traceback (CR-M5-P1-001).
    try:
        module_path = resolve_module_path(module_name)
        split_branch = resolve_split_branch(module_name)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    _print_info(f"Publishing module: {module_name}")
    _print_info(f"Module path: {module_path}")
    _print_info(f"Split branch: {split_branch}")
    print()

    _print_info("Running git subtree split...")
    try:
        split_sha = run_git_subtree_split(
            prefix=module_path,
            branch=split_branch,
            rejoin=True,
            ignore_joins=True,
            path=_REPO_ROOT,
            runner=runner,
        )
        _print_success(f"Git subtree split completed (SHA: {split_sha[:12]}...)")
    except GitError as e:
        _print_error(f"Git subtree split failed: {e}")
        if "cache for" in str(e) and "already exists" in str(e):
            _print_error("Git subtree split failed due to cache error.")
            _print_info("Try running with --clean to fix this:")
            _print_info(f"  {sys.argv[0]} {module_name} --clean")
        sys.exit(1)

    _print_info("Pushing split branch to origin...")
    try:
        push_split_branch(
            split_branch,
            remote="origin",
            expected_remote_sha=expected_remote_sha,
            path=_REPO_ROOT,
            runner=runner,
        )
        _print_success("Split branch pushed to origin")
    except GitError as e:
        _print_error(f"Failed to push split branch to origin: {e}")
        sys.exit(1)

    print()
    _print_success(f"Module '{module_name}' published successfully!")
    _print_info(f"Split branch: {split_branch}")
    _print_info(f"Users can now embed this module with: quickscale embed --module {module_name}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _show_provenance_diagnostics(runner: GitRunner) -> bool:
    """
    Report read-only release-provenance diagnostics (F2.9b).

    Inspects whether the source state is release-authoritative (VERSION matches
    a git tag at HEAD) and prints an operator-facing summary.  This is strictly
    read-only: it never fails closed and never exits, so operators can inspect
    untagged or mismatched split provenance without triggering the mutating
    F2.9a gate.

    Returns True when the source is release-authoritative, False otherwise.
    """
    is_auth, version, tag, reason = is_release_authoritative(_REPO_ROOT, runner=runner)
    if is_auth:
        _print_success(f"Release provenance: authoritative (VERSION={version}, tag={tag})")
        return True

    _print_warning(f"Release provenance: NOT authoritative (VERSION={version or 'unknown'})")
    if reason:
        _print_warning(f"  Reason: {reason}")
    _print_info("  Mutating publish flows are blocked until HEAD is tagged to match VERSION.")
    return False


def _show_status(
    runner: GitRunner,
    *,
    version: str | None = None,
    modules: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Show split-branch and peeled-tag status for one frozen module set."""
    if version is None:
        version = _read_repository_version()
    frozen_modules = list(_list_modules() if modules is None else modules)
    _warn_uncommitted_changes(runner)
    _print_info("Inspecting module publish status...")
    print()

    # F2.9b: read-only release-provenance diagnostic (never fails closed).
    is_auth = _show_provenance_diagnostics(runner)
    print()

    outdated: list[str] = []
    unpublished: list[str] = []

    all_sealed = True
    for module_name in frozen_modules:
        state, local_sha, pub_sha, pub_source = _get_module_publish_state(module_name, runner)
        seal_state = _get_module_seal_state(module_name, version, pub_sha, runner)
        if state == "up-to-date":
            print(f"  {module_name:<16} {seal_state} up to date ({pub_source}, {local_sha[:12]})")
        elif state == "outdated":
            print(
                f"  {module_name:<16} {seal_state} outdated "
                f"({pub_source}: local {local_sha[:12]} != published {pub_sha[:12]})"
            )
            outdated.append(module_name)
        elif state == "unpublished":
            print(
                f"  {module_name:<16} {seal_state} unpublished "
                f"(local {local_sha[:12]}, no split branch)"
            )
            unpublished.append(module_name)
        if seal_state != f"sealed@{version}":
            all_sealed = False

    print()
    if not outdated and not unpublished:
        _print_success("All module split branches are up to date.")
        if not is_auth:
            print()
            _print_info("Next action:")
            _print_info("  Tag HEAD to match VERSION before any mutating publish flow.")
        return all_sealed

    if outdated:
        _print_warning(f"Outdated split branches: {' '.join(outdated)}")
    if unpublished:
        _print_warning(f"Unpublished split branches: {' '.join(unpublished)}")

    # F2.9b: explicit next-action guidance (read-only; --status never fails closed).
    print()
    _print_info("Next actions:")
    if not is_auth:
        # NOTE: keep --status output free of the lowercase substring
        # "not release-authoritative"; the read-only status test asserts that
        # substring is absent so --status is never mistaken for the F2.9a gate.
        _print_info("  1. Tag HEAD to match VERSION so the source is release-authoritative.")
        _print_info("  2. Re-run single-module publish:")
        _print_info("       make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<40hex|ABSENT>")
    else:
        _print_info("  Publish each outdated module individually:")
        _print_info("    make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<40hex|ABSENT>")
    return all_sealed


def _publish_outdated(clean: bool, runner: GitRunner) -> None:
    """Publish only modules with missing or outdated split branches."""
    # F2.9a: Gate mutating flows on release-authoritative source state
    # This must fire BEFORE the uncommitted changes prompt so the gate
    # error is clear and does not get masked by interactive prompts.
    _check_release_authoritative(runner)

    if not _confirm_uncommitted_changes(runner):
        return

    _maybe_clean_subtree_cache(clean)

    queue: list[str] = []
    for module_name in _list_modules():
        state, *_ = _get_module_publish_state(module_name, runner)
        if state in ("outdated", "unpublished"):
            queue.append(module_name)

    if not queue:
        _print_success("All module split branches are already up to date.")
        return

    _print_info(f"Publishing outdated modules: {' '.join(queue)}")
    print()

    for module_name in queue:
        _publish_module(module_name, expected_remote_sha="ABSENT", runner=runner)
        print()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish module changes to split branches (F2.8 provenance-aware wrapper)."
    )
    parser.add_argument(
        "module_name",
        nargs="?",
        help="Module name to publish (e.g. auth, billing)",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--status",
        action="store_true",
        help="Show split-branch and seal status for every module",
    )
    actions.add_argument(
        "--seal",
        action="store_true",
        help="Seal one module's split branch at VERSION",
    )
    actions.add_argument(
        "--seal-all",
        action="store_true",
        help="Seal every authoritative module serially at VERSION",
    )
    parser.add_argument(
        "--publish-outdated",
        action="store_true",
        help=(
            "[DISABLED in SA117 Phase 4] Previously published modules with "
            "missing or outdated split branches.  Now exits with safety "
            "guidance; use single-module publish instead."
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear git subtree cache before splitting (publish only)",
    )
    parser.add_argument(
        "--version",
        metavar="VERSION",
        help="Release version for seal actions, or an explicit status version",
    )
    parser.add_argument(
        "--previous-version",
        metavar="VERSION",
        help="Optional prior release version for seal actions",
    )
    parser.add_argument(
        "--expected-remote-sha",
        help=(
            "Exact 40-char hex SHA expected on remote, or ABSENT for first publish. "
            "Required for single-module publish; rejected with --status."
        ),
    )
    parser.add_argument(
        "--git-executable",
        help=(
            "Absolute Git executable for publication, or omit to resolve git "
            "from PATH (QUICKSCALE_GIT_EXECUTABLE is also supported)."
        ),
    )
    return parser


def _validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject action/argument combinations before Git bootstrap or mutation."""
    if args.status:
        if args.module_name is not None:
            parser.error("--status does not accept a module name")
        if args.clean:
            parser.error("--clean is only supported with publish actions")
        if args.expected_remote_sha is not None:
            parser.error("--expected-remote-sha is not supported with --status")
        if args.previous_version is not None:
            parser.error("--previous-version is only supported with --seal or --seal-all")
        return

    if args.seal:
        if args.module_name is None:
            parser.error("--seal requires a module name")
        if args.version is None:
            parser.error("--seal requires --version VERSION")
        if args.clean:
            parser.error("--clean is only supported with publish actions")
        if args.expected_remote_sha is not None:
            parser.error("--expected-remote-sha is not supported with --seal")
        return

    if args.seal_all:
        if args.module_name is not None:
            parser.error("--seal-all does not accept a module name")
        if args.version is None:
            parser.error("--seal-all requires --version VERSION")
        if args.clean:
            parser.error("--clean is only supported with publish actions")
        if args.expected_remote_sha is not None:
            parser.error("--expected-remote-sha is not supported with --seal-all")
        return

    if args.publish_outdated:
        if args.module_name is not None:
            parser.error("--publish-outdated does not accept a module name")
        if args.version is not None:
            parser.error("--version is not supported with --publish-outdated")
        if args.previous_version is not None:
            parser.error("--previous-version is only supported with --seal or --seal-all")
        return

    if args.module_name is None and (args.clean or args.expected_remote_sha is not None):
        parser.error("publish options require a module name")
    if args.previous_version is not None:
        parser.error("--previous-version is only supported with --seal or --seal-all")
    if args.version is not None:
        parser.error("--version is only supported with --seal, --seal-all, or --status")


def _run_release_gates(runner: GitRunner) -> None:
    """Apply the existing release and origin gates with one trusted runner."""
    try:
        _check_release_authoritative(runner)
        validate_publication_origin(_REPO_ROOT, runner=runner)
    except GitError as exc:
        _print_error(f"Publication origin or release validation failed: {exc}")
        sys.exit(1)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _validate_cli_args(parser, args)

    # Validate repo root
    if not (_REPO_ROOT / "quickscale_modules").is_dir():
        _print_error(
            "quickscale_modules directory not found. Are you in the QuickScale repository root?"
        )
        sys.exit(1)

    # Bootstrap and validate the publication runner before the first Git
    # process.  In particular, a hostile PATH/config/repository environment
    # must not get an opportunity to influence the bootstrap probe itself.
    try:
        runner = build_publication_git_runner(args.git_executable)
    except GitError as e:
        _print_error(f"Publication Git bootstrap failed: {e}")
        sys.exit(1)

    if not is_git_repo(_REPO_ROOT, runner=runner):
        _print_error("Not a git repository")
        sys.exit(1)

    if args.status:
        _show_status(runner, version=args.version)
    elif args.seal:
        module_name = args.module_name
        assert module_name is not None
        assert args.version is not None
        try:
            validate_module_name(module_name)
        except GitError as exc:
            _print_error(str(exc))
            sys.exit(1)
        _require_authoritative_module(module_name)
        _run_release_gates(runner)
        if not _confirm_uncommitted_changes(runner):
            return
        try:
            _invoke_seal_module(
                module_name,
                args.version,
                previous_version=args.previous_version,
                runner=runner,
            )
        except GitError as exc:
            _print_error(f"Failed to seal module '{module_name}': {exc}")
            sys.exit(1)
        _print_success(f"Module '{module_name}' sealed at {args.version}")
    elif args.seal_all:
        assert args.version is not None
        # Freeze the authoritative inventory before any gate, prompt, or seal
        # operation.  The same set is used by the final read-only proof.
        frozen_modules = list(_list_modules())
        _run_release_gates(runner)
        if not _confirm_uncommitted_changes(runner):
            return
        try:
            _seal_all(
                args.version,
                previous_version=args.previous_version,
                runner=runner,
                modules=frozen_modules,
            )
        except (GitError, SystemExit) as exc:
            if isinstance(exc, SystemExit):
                raise
            _print_error(str(exc))
            sys.exit(1)
        if not _show_status(runner, version=args.version, modules=frozen_modules):
            _print_error("Seal-all verification did not produce a sealed status for every module")
            sys.exit(1)
    elif args.publish_outdated:
        _print_error("--publish-outdated is disabled in SA117 Phase 4")
        _print_info(
            "Batch --publish-outdated used bare --force, which violates the "
            "force-with-lease safety contract."
        )
        _print_info("Publish each module individually with --expected-remote-sha:")
        for name in _list_modules():
            _print_info(f"  make publish-module MODULE={name} EXPECTED_REMOTE_SHA=<40hex|ABSENT>")
        sys.exit(1)
    elif args.module_name:
        module_name = args.module_name

        # Phase 4: --expected-remote-sha is required for single-module publish
        expected_sha = args.expected_remote_sha
        if not expected_sha:
            _print_error(
                "--expected-remote-sha is required for single-module publish "
                "(use: --expected-remote-sha <40hex|ABSENT>)"
            )
            sys.exit(1)

        # Validate expected SHA format before any git operations
        try:
            validate_expected_sha(expected_sha)
        except GitError as e:
            _print_error(f"Invalid --expected-remote-sha: {e}")
            sys.exit(1)

        # Validate module name shape BEFORE any path resolution or subtree
        # operations so invalid input fails closed with a clean error instead
        # of an uncaught traceback (CR-M5-P1-001).
        try:
            validate_module_name(module_name)
        except GitError as e:
            _print_error(str(e))
            sys.exit(1)

        # F-002: reject any direct selection absent from the authoritative
        # shipped-module inventory before the release-authority gate, origin
        # validation, prompts, subtree split, or push.  A placeholder name
        # (teams) and an unapproved inventory addition (count drift) both
        # fail closed here, before any outward or mutating path.  This
        # supersedes the previous on-disk directory-existence check: the
        # authoritative inventory is the single source of truth for what a
        # direct selector may publish.
        _require_authoritative_module(module_name)

        # First enforce the existing release-authoritative gate so callers get
        # the established diagnostic for an untagged/mismatched source.  The
        # origin check immediately follows and remains before any prompt,
        # subtree split, or other mutation.
        _check_release_authoritative(runner)

        # This is the final pre-mutation source gate.  It checks effective
        # fetch and push identity while allowing unrelated remotes, and fails
        # closed for blank, mixed, or untrusted origin configuration.
        try:
            validate_publication_origin(_REPO_ROOT, runner=runner)
        except GitError as e:
            _print_error(f"Publication origin validation failed: {e}")
            sys.exit(1)

        if not _confirm_uncommitted_changes(runner):
            return

        _maybe_clean_subtree_cache(args.clean)
        _publish_module(
            module_name,
            expected_remote_sha=expected_sha,
            runner=runner,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
