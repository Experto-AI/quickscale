"""Git utilities for module management via git subtree operations."""

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, cast


class GitError(Exception):
    """Raised when a git operation fails."""

    pass


@dataclass(frozen=True)
class GitRunner:
    """Run Git with an optional, publication-scoped execution environment.

    The default helpers continue to invoke ``git`` directly when no runner is
    supplied.  Publication callers use a runner created by
    :func:`build_publication_git_runner`; this keeps the hardening controls out
    of unrelated module-management callers while ensuring every publication
    subprocess uses the same validated executable and environment.
    """

    executable: str = "git"
    env: Mapping[str, str] | None = None
    publication: bool = False

    def run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        """Run *args* without a shell, using this runner's executable/env."""
        run_kwargs = dict(kwargs)
        run_kwargs["env"] = dict(self.env) if self.env is not None else None
        run_kwargs["shell"] = False
        return subprocess.run([self.executable, *args], **run_kwargs)


_PUBLICATION_EXECUTABLE_ENV = "QUICKSCALE_GIT_EXECUTABLE"
_PUBLICATION_ENV_STRIP_EXACT = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DIR",
    "GIT_EXEC_PATH",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
}


def _publication_environment() -> dict[str, str]:
    """Return a sanitized environment for publication-only Git commands.

    Repository/config redirection and indexed ``GIT_CONFIG`` injection are
    removed.  Credential transports (for example ``SSH_AUTH_SOCK``,
    ``GIT_SSH_COMMAND``, credential helpers, and proxy settings) remain
    available; publication identity is enforced independently through the
    effective ``origin`` URLs.
    """
    env = os.environ.copy()
    for key in list(env):
        if (
            key in _PUBLICATION_ENV_STRIP_EXACT
            or key.startswith("GIT_CONFIG_KEY_")
            or key.startswith("GIT_CONFIG_VALUE_")
        ):
            env.pop(key, None)

    # These controls are intentionally explicit rather than inherited from a
    # user's shell.  Keep the repository-local config available, while
    # disabling system/global config and interactive credential prompts.
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_LITERAL_PATHSPECS"] = "1"
    return env


def build_publication_git_runner(
    executable: str | Path | None = None,
) -> GitRunner:
    """Validate and build the trusted runner used by publication Git calls.

    An explicit executable must be an absolute executable file.  Otherwise
    ``git`` is resolved through the normal ``PATH`` using :func:`shutil.which`.
    No Git subprocess is started until all executable and environment checks
    have completed.
    """
    requested = executable
    if requested is None:
        requested = os.environ.get(_PUBLICATION_EXECUTABLE_ENV)

    if requested is None:
        resolved = shutil.which("git")
        if resolved is None:
            raise GitError("Git executable 'git' was not found on PATH")
        executable_path = Path(resolved)
    else:
        requested_text = os.fspath(requested)
        if "\x00" in requested_text:
            raise GitError("Git executable contains an embedded NUL character")
        executable_path = Path(requested_text)
        if not executable_path.is_absolute():
            raise GitError(
                "Explicit Git executable must be an absolute executable path"
            )

    if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
        raise GitError(f"Git executable is not executable: {executable_path}")

    return GitRunner(
        executable=str(executable_path),
        env=_publication_environment(),
        publication=True,
    )


def _run_git(
    args: list[str],
    *,
    runner: GitRunner | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a Git command, preserving legacy defaults when no runner is given."""
    if runner is None:
        return subprocess.run(["git", *args], **kwargs)
    return runner.run(args, **kwargs)


def _parse_nul_records(output: bytes | str, *, description: str) -> list[bytes]:
    """Parse a Git NUL-delimited stream, rejecting ambiguous output."""
    raw = output.encode() if isinstance(output, str) else output
    if not raw:
        return []
    if not raw.endswith(b"\x00"):
        raise GitError(
            f"Malformed {description}: non-empty output is not NUL-terminated"
        )
    records = raw[:-1].split(b"\x00")
    if any(not record for record in records):
        raise GitError(f"Malformed {description}: empty NUL-delimited path")
    return records


# Strict module-name allowlist: alphanumeric, hyphens, underscores; must start
# with an alphanumeric character.  This prevents path-traversal (``..``, ``/``),
# flag-injection (``-leading``), and shell-meta characters from reaching
# ``git subtree --prefix=`` or branch-name arguments.
_MODULE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_module_name(module_name: str) -> None:
    """Reject *module_name* unless it is a safe bare slug.

    Raises :class:`GitError` with an operator-facing message when the name is
    empty, contains path separators, starts with ``-``, or includes any
    character outside ``[a-zA-Z0-9_-]``.
    """
    if not module_name:
        raise GitError("Module name must not be empty")
    if not _MODULE_NAME_RE.match(module_name):
        raise GitError(
            f"Invalid module name {module_name!r}; "
            "expected a bare slug matching [a-zA-Z0-9][a-zA-Z0-9_-]*"
        )


def is_git_repo(path: Path | None = None, *, runner: GitRunner | None = None) -> bool:
    """Check if current directory or specified path is a git repository"""
    cwd = path or Path.cwd()
    try:
        _run_git(
            ["rev-parse", "--git-dir"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            runner=runner,
        )
        return True
    except subprocess.CalledProcessError, FileNotFoundError:
        return False


def is_working_directory_clean(
    path: Path | None = None, *, runner: GitRunner | None = None
) -> bool:
    """Check if there are uncommitted changes in the git working directory"""
    cwd = path or Path.cwd()
    try:
        result = _run_git(
            [
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
                "-z",
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=False,
            runner=runner,
        )
        return not _parse_nul_records(
            result.stdout, description="git status porcelain output"
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check git status: {e.stderr}")


def check_remote_branch_exists(
    remote: str, branch: str, path: Path | None = None
) -> bool:
    """Check if branch exists on remote repository"""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", remote, branch],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check remote branch: {e.stderr}")


def run_git_subtree_add(
    prefix: str,
    remote: str,
    branch: str,
    squash: bool = True,
    path: Path | None = None,
) -> None:
    """Execute git subtree add with error handling.

    The *branch* parameter accepts either a branch name or a fully-spelled
    40-character hex commit SHA.  Passing a SHA binds the add to the exact
    commit so the fetched content cannot drift if the remote branch advances
    between ref resolution and the subtree operation.  This relies on
    ``git fetch <url> <hex>`` officially supporting fully-spelled hex object
    names and ``git-subtree`` forwarding the ref to ``git fetch``.  Verified
    on Git 2.43.0+.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "add", f"--prefix={prefix}", remote, branch]
    if squash:
        cmd.append("--squash")

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to add git subtree: {e.stderr}")


def run_git_subtree_pull(
    prefix: str, remote: str, branch: str, squash: bool = True, path: Path | None = None
) -> str:
    """Execute git subtree pull with error handling and return diff summary.

    The *branch* parameter accepts either a branch name or a fully-spelled
    40-character hex commit SHA.  Passing a SHA binds the pull to the exact
    commit so the fetched content cannot drift if the remote branch advances
    between ref resolution and the subtree operation.

    This SHA-pinned contract is verified by the integration test
    ``TestSubtreePullWithCommitSha`` in ``quickscale_core/tests/test_git_utils.py``
    and relies on ``git fetch <url> <hex>`` officially supporting fully-spelled
    hex object names (git-fetch documentation) and ``git-subtree`` forwarding
    the ref to ``git fetch``.  Verified on Git 2.43.0+.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "pull", f"--prefix={prefix}", remote, branch]
    if squash:
        cmd.append("--squash")

    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=True, capture_output=True, text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to pull git subtree: {e.stderr}")


def run_git_subtree_push(
    prefix: str, remote: str, branch: str, path: Path | None = None
) -> None:
    """Execute git subtree push with error handling"""
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "push", f"--prefix={prefix}", remote, branch]

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push git subtree: {e.stderr}")


def resolve_remote_ref(remote: str, branch: str, path: Path | None = None) -> str:
    """Resolve a remote branch to its current commit SHA.

    Uses ``git ls-remote`` to look up the tip of *branch* on *remote* and
    returns the full 40-character hex SHA.  This lets callers bind the
    exact source ref once and reuse it for both the subtree operation and
    state persistence.

    Args:
        remote: Git remote URL.
        branch: Branch name on the remote (e.g. ``splits/auth-module``).
        path: Optional working directory for the git command.

    Returns:
        The 40-character hex commit SHA string.

    Raises:
        GitError: If the remote cannot be contacted or the branch does not
            exist on the remote.
    """
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", remote, branch],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to resolve remote ref: {e.stderr}") from e

    output = result.stdout.strip()
    if not output:
        raise GitError(
            f"Remote branch '{branch}' not found on {remote}; cannot resolve source ref"
        )

    # ls-remote output format: "<sha>\trefs/heads/<branch>"
    sha = output.split()[0]
    if len(sha) != 40:
        raise GitError(f"Unexpected ref format from ls-remote for {branch}: {sha!r}")
    return sha


def get_remote_url(
    remote_name: str = "origin",
    path: Path | None = None,
    *,
    runner: GitRunner | None = None,
) -> str:
    """Get the URL of a git remote"""
    cwd = path or Path.cwd()
    try:
        result = _run_git(
            ["remote", "get-url", remote_name],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            runner=runner,
        )
        return cast(str, result.stdout).strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get remote URL: {e.stderr}")


_TRUSTED_PUBLICATION_ORIGIN_URLS = frozenset(
    {
        "https://github.com/Experto-AI/quickscale",
        "https://github.com/Experto-AI/quickscale.git",
        "git@github.com:Experto-AI/quickscale",
        "git@github.com:Experto-AI/quickscale.git",
        "ssh://git@github.com/Experto-AI/quickscale",
        "ssh://git@github.com/Experto-AI/quickscale.git",
    }
)


def _publication_origin_identity(url: str) -> str | None:
    """Return the reviewed repository identity for an exact URL spelling."""
    if url in _TRUSTED_PUBLICATION_ORIGIN_URLS:
        return "github.com/Experto-AI/quickscale"
    return None


def _effective_remote_url_args(remote_name: str, *, push: bool) -> list[str]:
    """Build the Git arguments for reading effective remote URLs."""
    args = ["remote", "get-url"]
    if push:
        args.append("--push")
    args.extend(["--all", remote_name])
    return args


def _effective_remote_url_kind(*, push: bool) -> str:
    """Return the operator-facing URL kind for a fetch or push lookup."""
    return "push" if push else "fetch"


def _raise_effective_remote_url_error(
    error: subprocess.CalledProcessError,
    *,
    push: bool,
) -> None:
    """Translate a failed effective-URL lookup into a stable Git error."""
    kind = _effective_remote_url_kind(push=push)
    stderr = error.stderr or ""
    if "No such remote" in stderr or "does not appear" in stderr:
        raise GitError(f"Origin {kind} URL is blank or unset") from error
    raise GitError(
        f"Failed to read origin {kind} URL: {stderr or 'remote is unavailable'}"
    ) from error


def _validate_effective_remote_urls(urls: list[str], *, push: bool) -> list[str]:
    """Reject missing, blank, or whitespace-padded effective remote URLs."""
    kind = _effective_remote_url_kind(push=push)
    if not urls or any(not url for url in urls):
        raise GitError(f"Origin {kind} URL is blank or unset")
    for url in urls:
        stripped_url = url.strip()
        if not stripped_url:
            raise GitError(f"Origin {kind} URL is blank or unset")
        if url != stripped_url:
            raise GitError(
                f"Origin {kind} URL contains surrounding whitespace and is untrusted"
            )
    return urls


def _get_effective_remote_urls(
    remote_name: str,
    *,
    push: bool,
    path: Path,
    runner: GitRunner | None,
) -> list[str]:
    """Read all effective fetch or push URLs for one remote."""
    try:
        result = _run_git(
            _effective_remote_url_args(remote_name, push=push),
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
            runner=runner,
        )
    except subprocess.CalledProcessError as e:
        _raise_effective_remote_url_error(e, push=push)

    urls = result.stdout.splitlines()
    return _validate_effective_remote_urls(urls, push=push)


def validate_publication_origin(
    path: Path,
    *,
    remote_name: str = "origin",
    runner: GitRunner | None = None,
) -> tuple[str, str]:
    """Require exact trusted fetch and push identities for publication.

    Only the named remote is checked, so unrelated remotes remain allowed.
    Every effective URL configured for that remote must be one of the explicit
    HTTPS/SSH forms for ``github.com/Experto-AI/quickscale`` and fetch/push
    identities must agree.  A missing push URL is handled by Git's effective
    URL resolution, which reports the fetch URL as the push URL.
    """
    fetch_urls = _get_effective_remote_urls(
        remote_name, push=False, path=path, runner=runner
    )
    push_urls = _get_effective_remote_urls(
        remote_name, push=True, path=path, runner=runner
    )

    fetch_identities = {_publication_origin_identity(url) for url in fetch_urls}
    push_identities = {_publication_origin_identity(url) for url in push_urls}
    if None in fetch_identities:
        raise GitError(
            "Publication origin fetch URL is not the trusted "
            "github.com/Experto-AI/quickscale repository"
        )
    if None in push_identities:
        raise GitError(
            "Publication origin push URL is not the trusted "
            "github.com/Experto-AI/quickscale repository"
        )

    # Compare repository identity, not transport spelling: HTTPS and SSH are
    # both authorized, but fetch and push must target the same exact project.
    if fetch_identities != push_identities:
        raise GitError("Publication origin fetch and push identities differ")
    return fetch_urls[0], push_urls[0]


def assert_staged_index_empty(
    path: Path | None = None,
    *,
    runner: GitRunner | None = None,
) -> None:
    """Fail unless the index has no staged paths, using filename-safe NUL I/O."""
    cwd = path or Path.cwd()
    try:
        result = _run_git(
            ["diff", "--cached", "--name-only", "-z", "--"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=False,
            runner=runner,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to inspect staged index: {e.stderr}") from e

    staged_paths = _parse_nul_records(
        result.stdout, description="cached Git path output"
    )
    if staged_paths:
        raise GitError(
            f"Staged index is not empty ({len(staged_paths)} staged path(s)); "
            "publication aborted"
        )


# ---------------------------------------------------------------------------
# F2.8 — Provenance-aware split-publish helper surface
# ---------------------------------------------------------------------------


def resolve_module_path(module_name: str) -> str:
    """Return the canonical maintainer-side module path for *module_name*.

    Centralizes the ``quickscale_modules/<name>`` convention so split-publish
    callers do not hardcode the path template.  Raises :class:`GitError` when
    *module_name* is not a valid bare module slug (empty, path separators,
    ``..`` traversal, flag-injection prefixes, or shell-meta characters).
    """
    validate_module_name(module_name)
    return f"quickscale_modules/{module_name}"


def resolve_split_branch(module_name: str) -> str:
    """Return the canonical split branch name for *module_name*.

    Centralizes the ``splits/<name>-module`` convention so split-publish
    callers do not hardcode the branch template.  Raises :class:`GitError`
    when *module_name* is not a valid bare module slug (empty, path
    separators, ``..`` traversal, flag-injection prefixes, or shell-meta
    characters).
    """
    validate_module_name(module_name)
    return f"splits/{module_name}-module"


def resolve_split_tag(module_name: str, version: str) -> str:
    """Return the canonical immutable tag for a module split.

    Split tags use the split branch name as a namespace and the canonical
    three-component core version as their suffix.  The version parser is
    shared with manifest validation so tag construction cannot drift from the
    lockstep version contract.
    """
    # Keep this import lazy: publication wrapper smoke tests intentionally use
    # a minimal copied ``git_utils.py`` without the full manifest package.
    from quickscale_core.manifest.loader import _parse_canonical_version_triple

    try:
        major, minor, patch = _parse_canonical_version_triple(version)
    except (AttributeError, TypeError, ValueError) as e:
        raise GitError(f"Invalid canonical version {version!r}: {e}") from e
    return f"{resolve_split_branch(module_name)}/{major}.{minor}.{patch}"


def validate_tag_name(tag: str) -> None:
    """Reject tag values that are not one literal, valid Git ref name.

    Tag values are interpolated into explicit ``refs/tags`` arguments and
    refspecs.  Keep this validation local and deterministic so malformed,
    wildcard, or option-like values cannot reach a Git subprocess.
    """
    if not isinstance(tag, str) or not tag:
        raise GitError("Tag name must not be empty")
    if tag.startswith("-"):
        raise GitError(f"Invalid tag name {tag!r}; option-like values are not allowed")
    if tag.startswith("refs/"):
        raise GitError(f"Invalid tag name {tag!r}; expected a tag name, not a full ref")
    if tag == "@" or "@{" in tag:
        raise GitError(f"Invalid tag name {tag!r}; malformed Git ref")
    if ".." in tag or tag.endswith(".") or tag.endswith(".lock"):
        raise GitError(f"Invalid tag name {tag!r}; malformed Git ref")
    if (
        tag.startswith("/")
        or tag.endswith("/")
        or "//" in tag
        or any(part.startswith(".") or part.endswith(".") for part in tag.split("/"))
    ):
        raise GitError(f"Invalid tag name {tag!r}; malformed Git ref")
    if any(
        character.isspace()
        or ord(character) < 0x20
        or ord(character) == 0x7F
        or character in "~^:?*[\\"
        for character in tag
    ):
        raise GitError(
            f"Invalid tag name {tag!r}; wildcard, control, or ref-special "
            "characters are not allowed"
        )


_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _validate_commit_sha(sha: str, *, description: str) -> str:
    """Validate and return a full, non-ambiguous Git object SHA."""
    if not _SHA_RE.fullmatch(sha):
        raise GitError(f"Unexpected {description}: {sha!r}; expected a 40-hex SHA")
    return sha


def _resolve_remote_tag_commit(
    remote: str, tag: str, path: Path | None = None
) -> str | None:
    """Resolve a remote tag, returning ``None`` when the tag is absent."""
    validate_tag_name(tag)
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            [
                "git",
                "ls-remote",
                "--tags",
                "--",
                remote,
                f"refs/tags/{tag}",
                f"refs/tags/{tag}^{{}}",
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to resolve remote tag '{tag}': {e.stderr}") from e

    expected_direct_ref = f"refs/tags/{tag}"
    expected_peeled_ref = f"{expected_direct_ref}^{{}}"
    direct_sha: str | None = None
    peeled_sha: str | None = None
    output = result.stdout
    if not output:
        return None
    for line in output.splitlines():
        if not line.strip():
            raise GitError(f"Malformed ls-remote tag output for {tag!r}: blank record")
        fields = line.split("\t")
        if len(fields) != 2:
            raise GitError(f"Malformed ls-remote tag output for {tag!r}: {line!r}")
        sha, ref = fields
        if ref == expected_peeled_ref:
            if peeled_sha is not None:
                raise GitError(
                    f"Malformed ls-remote tag output for {tag!r}: "
                    "duplicate peeled record"
                )
            peeled_sha = _validate_commit_sha(sha, description=f"peeled tag {tag}")
        elif ref == expected_direct_ref:
            if direct_sha is not None:
                raise GitError(
                    f"Malformed ls-remote tag output for {tag!r}: "
                    "duplicate direct record"
                )
            direct_sha = _validate_commit_sha(sha, description=f"tag {tag}")
        else:
            raise GitError(
                f"Malformed ls-remote tag output for {tag!r}: unknown ref {ref!r}"
            )

    if direct_sha is None:
        raise GitError(
            f"Malformed ls-remote tag output for {tag!r}: peeled record without direct record"
        )
    return peeled_sha or direct_sha


def resolve_remote_tag(remote: str, tag: str, path: Path | None = None) -> str:
    """Resolve *tag* on *remote* to its peeled 40-hex commit SHA.

    Annotated tags are returned via their ``^{{}}`` peeled entry.  Lightweight
    tags use the direct entry.  A missing tag is an error rather than a
    fallback to another ref.
    """
    commit_sha = _resolve_remote_tag_commit(remote, tag, path)
    if commit_sha is None:
        raise GitError(f"Remote tag '{tag}' not found on {remote}")
    return commit_sha


def check_remote_tag_exists(remote: str, tag: str, path: Path | None = None) -> bool:
    """Return whether *tag* exists on *remote* without resolving another ref."""
    return _resolve_remote_tag_commit(remote, tag, path) is not None


def get_tree_sha(commit: str, path: Path | None = None) -> str:
    """Return the tree SHA for *commit* using Git's verified tree peel."""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{commit}^{{tree}}"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to resolve tree for {commit}: {e.stderr}") from e
    return _validate_commit_sha(result.stdout.strip(), description="tree")


def get_local_tag_commit(tag: str, path: Path | None = None) -> str | None:
    """Return the commit resolved by a local tag, or ``None`` if absent."""
    validate_tag_name(tag)
    cwd = path or Path.cwd()
    tag_ref = f"refs/tags/{tag}"
    try:
        presence = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", tag_ref],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        raise GitError(f"Failed to inspect local tag '{tag}': {e}") from e
    if presence.returncode == 1:
        return None
    if presence.returncode != 0:
        raise GitError(
            f"Failed to inspect local tag '{tag}': "
            f"{presence.stderr or 'git returned a non-zero status'}"
        )

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{tag_ref}^{{commit}}"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        raise GitError(f"Failed to resolve local tag '{tag}': {e}") from e
    if result.returncode != 0:
        raise GitError(
            f"Failed to resolve local tag '{tag}': "
            f"{result.stderr or 'git returned a non-zero status'}"
        )
    return _validate_commit_sha(result.stdout.strip(), description=f"tag {tag}")


def create_annotated_tag(tag: str, commit: str, path: Path | None = None) -> None:
    """Create an annotated local tag, accepting only an identical existing tag.

    The absence of a force option is intentional: a local tag can be reused
    only when it already resolves to the requested commit.  A conflicting tag
    fails closed and reports both commit SHAs.
    """
    validate_tag_name(tag)
    requested_sha = _validate_commit_sha(commit, description="requested commit")
    existing_sha = get_local_tag_commit(tag, path)
    if existing_sha is not None:
        if existing_sha == requested_sha:
            return
        raise GitError(
            f"Local tag '{tag}' resolves to {existing_sha}, requested {requested_sha}"
        )

    cwd = path or Path.cwd()
    try:
        subprocess.run(
            ["git", "tag", "--annotate", tag, requested_sha, "--message", tag],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to create annotated tag '{tag}': {e.stderr}") from e


def push_tag(tag: str, remote: str = "origin", path: Path | None = None) -> None:
    """Push exactly one tag ref without force flags or tag sweeping."""
    validate_tag_name(tag)
    cwd = path or Path.cwd()
    refspec = f"refs/tags/{tag}:refs/tags/{tag}"
    try:
        subprocess.run(
            ["git", "push", "--", remote, refspec],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push tag '{tag}': {e.stderr}") from e


def run_git_subtree_split(
    prefix: str,
    branch: str,
    *,
    rejoin: bool = True,
    ignore_joins: bool = True,
    path: Path | None = None,
    runner: GitRunner | None = None,
) -> str:
    """Execute ``git subtree split`` and return the resulting commit SHA.

    Creates or updates the local split *branch* from the subtree at *prefix*.
    The *rejoin* and *ignore_joins* flags match the provenance-aware split
    convention used by the maintainer publish workflow (F2.8).

    Returns:
        The 40-character hex commit SHA of the split result.

    Raises:
        GitError: If the subtree split fails.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "split", f"--prefix={prefix}", "-b", branch]
    if rejoin:
        cmd.append("--rejoin")
    if ignore_joins:
        cmd.append("--ignore-joins")

    try:
        result = _run_git(
            cmd[1:], cwd=cwd, check=True, capture_output=True, text=True, runner=runner
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to split git subtree: {e.stderr}") from e

    # ``git subtree split -b <branch>`` prints the resulting SHA to stdout.
    split_sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if not split_sha or len(split_sha) != 40:
        raise GitError(
            f"Unexpected subtree split output for {prefix}; "
            f"could not extract a 40-char SHA (got {split_sha!r})"
        )
    return split_sha


def validate_expected_sha(expected_remote_sha: str) -> None:
    """Validate an expected-remote-SHA value for force-with-lease safety.

    *expected_remote_sha* must be exactly one of:
    - A 40-character hex SHA (rejects all-zero and non-hex strings).
    - The literal string ``"ABSENT"`` (meaning no known previous SHA).

    Raises :class:`GitError` with an operator-facing message when the value
    is malformed.
    """
    if not expected_remote_sha:
        raise GitError("expected_remote_sha must not be empty")
    if expected_remote_sha == "ABSENT":
        return
    if len(expected_remote_sha) != 40:
        raise GitError(
            f"expected_remote_sha must be exactly 40 hex characters or 'ABSENT'; "
            f"got {len(expected_remote_sha)}-char value"
        )
    if not all(c in "0123456789abcdefABCDEF" for c in expected_remote_sha):
        raise GitError(
            f"expected_remote_sha contains non-hex characters: {expected_remote_sha!r}"
        )
    if all(c == "0" for c in expected_remote_sha):
        raise GitError("expected_remote_sha must not be all-zero")


def push_split_branch(
    branch: str,
    remote: str = "origin",
    *,
    expected_remote_sha: str | None = None,
    path: Path | None = None,
    runner: GitRunner | None = None,
) -> None:
    """Push a split *branch* to *remote* using force-with-lease safety.

    When *expected_remote_sha* is provided, the push uses
    ``--force-with-lease`` instead of bare ``--force``:

    - A 40-character hex SHA produces
      ``--force-with-lease=refs/heads/<branch>:<sha>``, which rejects the
      push if the remote ref has moved away from the expected commit.
    - The literal ``"ABSENT"`` produces plain ``--force-with-lease`` (no
      refspec), which protects only refs that have a tracking ref.

    When *expected_remote_sha* is ``None``, the push is performed without
    any ``--force`` flag (fast-forward-only).  Callers that require
    force-capable pushes **must** provide ``expected_remote_sha`` (SA117
    Phase 4).  The legacy bare ``--force`` fallback has been removed.

    Raises:
        GitError: If validation fails or the push fails.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "push"]

    if expected_remote_sha is not None:
        validate_expected_sha(expected_remote_sha)
        if expected_remote_sha == "ABSENT":
            cmd.append("--force-with-lease")
        else:
            cmd.append(f"--force-with-lease=refs/heads/{branch}:{expected_remote_sha}")

    cmd.extend([remote, branch])

    try:
        if runner is not None and runner.publication:
            assert_staged_index_empty(path=cwd, runner=runner)

        _run_git(
            cmd[1:], cwd=cwd, check=True, capture_output=True, text=True, runner=runner
        )

        if runner is not None and runner.publication:
            assert_staged_index_empty(path=cwd, runner=runner)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push split branch {branch}: {e.stderr}") from e


# ---------------------------------------------------------------------------
# F2.9a — Release-authoritative source gate
# ---------------------------------------------------------------------------


def read_version_file(repo_root: Path) -> str:
    """Read and return the trimmed version string from the VERSION file.

    Raises:
        GitError: If the VERSION file does not exist or cannot be read.
    """
    version_file = repo_root / "VERSION"
    if not version_file.is_file():
        raise GitError(f"VERSION file not found at {version_file}")
    try:
        content = version_file.read_text(encoding="utf-8")
        # Match the publish workflow's trimming: strip CR, leading/trailing whitespace
        version = content.replace("\r", "").strip()
        if not version:
            raise GitError("VERSION file is empty")
        return version
    except OSError as e:
        raise GitError(f"Failed to read VERSION file: {e}") from e


def get_all_tags_at_head(
    path: Path | None = None, *, runner: GitRunner | None = None
) -> list[str]:
    """Return all tag names pointing at HEAD (may be empty if untagged).

    Uses ``git tag --points-at HEAD`` to find tags that point directly at
    the current commit.  Works with both lightweight and annotated tags.
    Returns all tags if multiple tags point at HEAD, or an empty list if no
    tags point at HEAD.

    Raises:
        GitError: If the git command fails.
    """
    cwd = path or Path.cwd()
    try:
        result = _run_git(
            ["tag", "--points-at", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            runner=runner,
        )
        if result.returncode != 0:
            raise GitError(f"Failed to get tags at HEAD: {result.stderr}")
        tags = result.stdout.strip().splitlines()
        return [t for t in tags if t]
    except FileNotFoundError as e:
        raise GitError(f"git command not found: {e}") from e


def get_tag_at_head(
    path: Path | None = None, *, runner: GitRunner | None = None
) -> str | None:
    """Return the tag name pointing at HEAD, or None if HEAD is untagged.

    Uses ``git tag --points-at HEAD`` to find tags that point directly at
    the current commit.  Works with both lightweight and annotated tags.
    Returns the first tag if multiple tags point at HEAD, or None if no
    tags point at HEAD.

    Raises:
        GitError: If the git command fails.
    """
    tags = get_all_tags_at_head(path, runner=runner)
    return tags[0] if tags else None


def is_release_authoritative(
    repo_root: Path,
    *,
    runner: GitRunner | None = None,
) -> tuple[bool, str, str | None, str | None]:
    """Check if the source state is release-authoritative (F2.9a).

    Release-authoritative means the VERSION file content matches at least one
    git tag pointing at HEAD using one of the two workflow-authoritative tag
    forms (see .github/workflows/publish.yml):

    * exact VERSION match (e.g. ``0.86.0``), or
    * single lowercase ``v`` prefix + VERSION (e.g. ``v0.86.0``).

    Uppercase ``V``, multiple ``v`` prefixes, and other tag shapes are **not**
    accepted — they do not trigger the publish workflow and must not be treated
    as release-authoritative here either.  When multiple tags point at HEAD,
    the gate succeeds if *any* of them matches VERSION in one of these two
    forms — this prevents a stale or unrelated tag from shadowing a valid
    release tag.

    Returns:
        A tuple ``(is_authoritative, version_from_file, tag_at_head, mismatch_reason)``:
        - ``is_authoritative``: True if VERSION matches at least one tag at HEAD
        - ``version_from_file``: The version string from the VERSION file
        - ``tag_at_head``: The matching tag name, or the first tag if none match,
          or None if untagged
        - ``mismatch_reason``: Human-readable reason if not authoritative, or None

    This function does not raise on expected conditions (missing VERSION, untagged
    HEAD, version mismatch).  It returns structured diagnostics so callers can
    decide how to report or handle the situation.
    """
    try:
        version_from_file = read_version_file(repo_root)
    except GitError as e:
        return False, "", None, str(e)

    tags_at_head = get_all_tags_at_head(repo_root, runner=runner)

    if not tags_at_head:
        return (
            False,
            version_from_file,
            None,
            f"HEAD is not tagged; VERSION file contains {version_from_file}",
        )

    # Check each tag against the two workflow-authoritative forms only:
    # exact VERSION (e.g. "0.86.0") or single lowercase v + VERSION
    # (e.g. "v0.86.0").  Uppercase V, multiple v prefixes, and other shapes
    # do not trigger the publish workflow and must not match here either.
    # The gate succeeds if ANY tag matches VERSION in one of these forms.
    def _is_authoritative_tag(tag: str) -> bool:
        return tag == version_from_file or tag == f"v{version_from_file}"

    for tag in tags_at_head:
        if _is_authoritative_tag(tag):
            return True, version_from_file, tag, None

    # No tag matched.  Report the first tag in the mismatch reason for
    # operator clarity, but note if multiple tags were present.
    first_tag = tags_at_head[0]
    # Compute the stripped form for diagnostic parity with prior messages.
    first_version = first_tag.lstrip("vV")
    if len(tags_at_head) > 1:
        return (
            False,
            version_from_file,
            first_tag,
            f"VERSION file ({version_from_file}) does not match any of the "
            f"{len(tags_at_head)} tags at HEAD "
            f"(e.g. {first_tag} -> {first_version})",
        )
    return (
        False,
        version_from_file,
        first_tag,
        f"VERSION file ({version_from_file}) does not match tag at HEAD "
        f"({first_tag} -> {first_version})",
    )
