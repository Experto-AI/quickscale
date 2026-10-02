"""Git runner construction and safe subprocess plumbing.

Owns the optional publication-scoped :class:`GitRunner` execution
environment, its validation entry point, and the NUL-delimited IO helpers
shared by the repository and publication checks. Re-exported from
``quickscale_core.utils.git_utils``.
"""

from dataclasses import dataclass
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from quickscale_core.utils.git_errors import GitError


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
        return subprocess.run([self.executable, *args], **run_kwargs)  # noqa: S603 - fixed argv list, shell disabled


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
    removed.  Transport environment (for example ``SSH_AUTH_SOCK``,
    ``GIT_SSH_COMMAND``, and proxy settings) remains available, but system and
    global Git configuration do not.  Publication callers must therefore pass
    :func:`validate_publication_local_config` before mutation so credentials
    and commit identity come only from explicit repository-local config.
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


_PUBLICATION_LOCAL_CONFIG_COMMANDS = {
    "credential.helper": "git config --local credential.helper '<credential-helper>'",
    "user.name": "git config --local user.name '<name>'",
    "user.email": "git config --local user.email '<email>'",
}


def validate_publication_local_config(
    path: Path,
    *,
    runner: GitRunner,
) -> None:
    """Require publication credentials and identity in repository-local config.

    Publication deliberately disables system and global Git configuration.
    Each required value is therefore read with ``git config --local`` through
    the sanitized runner.  Missing and blank values are reported together so
    an operator receives one complete, actionable pre-mutation failure.
    """
    missing: list[str] = []
    for key in _PUBLICATION_LOCAL_CONFIG_COMMANDS:
        try:
            result = runner.run(
                ["config", "--local", "--get", key],
                cwd=path,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise GitError(
                f"Failed to read repository-local Git config {key!r}: {exc}"
            ) from exc

        if result.returncode == 1 or (
            result.returncode == 0 and not result.stdout.strip()
        ):
            missing.append(key)
            continue
        if result.returncode != 0:
            detail = result.stderr.strip() or "git returned a non-zero status"
            raise GitError(
                f"Failed to read repository-local Git config {key!r}: {detail}"
            )

    if not missing:
        return

    commands = "\n".join(
        f"  {_PUBLICATION_LOCAL_CONFIG_COMMANDS[key]}" for key in missing
    )
    raise GitError(
        "Publication requires repository-local Git credentials and identity "
        "because system/global Git config is disabled. "
        f"Missing or blank: {', '.join(missing)}.\n"
        "Configure the missing values in this repository before retrying:\n"
        f"{commands}"
    )


def _run_git(
    args: list[str],
    *,
    runner: GitRunner | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a Git command, preserving legacy defaults when no runner is given."""
    if runner is None:
        return subprocess.run(["git", *args], **kwargs)  # noqa: S603, S607 - fixed argv list, shell disabled; PATH-resolved executable by design
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
