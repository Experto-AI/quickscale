"""Unit tests for git utilities."""

import shlex
import shutil
import stat
import subprocess
import sys
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ``quickscale_core/pyproject.toml`` is the pytest config root when this file
# is selected directly, so the monorepo root is not otherwise importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import publish_module  # noqa: E402
from scripts.publish_module import _has_uncommitted_changes  # noqa: E402

from quickscale_core.utils.git_utils import (  # noqa: E402
    GitError,
    GitRunner,
    assert_staged_index_empty,
    build_publication_git_runner,
    check_remote_branch_exists,
    check_remote_tag_exists,
    get_all_tags_at_head,
    get_remote_url,
    get_local_tag_commit,
    get_tree_sha,
    get_tag_at_head,
    is_git_repo,
    is_release_authoritative,
    is_working_directory_clean,
    push_split_branch,
    push_tag,
    read_version_file,
    resolve_module_path,
    resolve_remote_ref,
    resolve_remote_tag,
    resolve_split_branch,
    resolve_split_tag,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
    run_git_subtree_split,
    create_annotated_tag,
    validate_publication_origin,
    validate_expected_sha,
    validate_module_name,
    validate_tag_name,
)


_AUTHORITATIVE_FIXTURE_MODULES = (
    "analytics",
    "auth",
    "backups",
    "billing",
    "blog",
    "crm",
    "forms",
    "listings",
    "notifications",
    "orgs",
    "social",
    "storage",
)


def _add_authoritative_module_contract(repo_dir: Path) -> None:
    """Add the module-discovery contract and its manifest-backed inventory."""
    contracts_dir = (
        repo_dir / "quickscale_core" / "src" / "quickscale_core" / "contracts"
    )
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "__init__.py").write_text("")
    real_repo_root = Path(__file__).resolve().parent.parent.parent
    real_module_discovery = (
        real_repo_root
        / "quickscale_core"
        / "src"
        / "quickscale_core"
        / "contracts"
        / "module_discovery.py"
    )
    # Copy rather than symlink so module discovery resolves the hermetic repo's
    # quickscale_modules/ tree instead of the checkout containing this test.
    (contracts_dir / "module_discovery.py").write_text(
        real_module_discovery.read_text()
    )

    modules_dir = repo_dir / "quickscale_modules"
    for module_name in _AUTHORITATIVE_FIXTURE_MODULES:
        module_dir = modules_dir / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "__init__.py").write_text("# fake module\n")
        (module_dir / "module.yml").write_text(f"name: {module_name}\n")


def _git_available() -> bool:
    """Return True if git is available on PATH."""
    return shutil.which("git") is not None


class TestIsGitRepo:
    """Tests for is_git_repo function"""

    @patch("subprocess.run")
    def test_is_git_repo_when_valid_repo(self, mock_run: MagicMock) -> None:
        """Test detecting a valid git repository"""
        mock_run.return_value = MagicMock(returncode=0)
        assert is_git_repo() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_is_git_repo_when_not_repo(self, mock_run: MagicMock) -> None:
        """Test detecting when not a git repository"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert is_git_repo() is False

    @patch("subprocess.run")
    def test_is_git_repo_with_custom_path(self, mock_run: MagicMock) -> None:
        """Test checking git repo with custom path"""
        mock_run.return_value = MagicMock(returncode=0)
        custom_path = Path("/custom/path")
        is_git_repo(custom_path)
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["cwd"] == custom_path


class TestIsWorkingDirectoryClean:
    """Tests for is_working_directory_clean function"""

    @patch("subprocess.run")
    def test_clean_working_directory(self, mock_run: MagicMock) -> None:
        """Test detecting clean working directory"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        assert is_working_directory_clean() is True

    @patch("subprocess.run")
    def test_dirty_working_directory(self, mock_run: MagicMock) -> None:
        """Test detecting dirty working directory"""
        mock_run.return_value = MagicMock(stdout=b"M  file.py\0", returncode=0)
        assert is_working_directory_clean() is False

    @patch("subprocess.run")
    def test_malformed_status_stream_fails_closed(self, mock_run: MagicMock) -> None:
        """A non-empty status stream without its final NUL is rejected."""
        mock_run.return_value = MagicMock(stdout=b"M  file.py", returncode=0)
        with pytest.raises(GitError, match="Malformed git status"):
            is_working_directory_clean()

    @patch("subprocess.run")
    def test_git_status_failure(self, mock_run: MagicMock) -> None:
        """Test handling git status command failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        with pytest.raises(GitError, match="Failed to check git status"):
            is_working_directory_clean()


class TestCheckRemoteBranchExists:
    """Tests for check_remote_branch_exists function"""

    @patch("subprocess.run")
    def test_branch_exists(self, mock_run: MagicMock) -> None:
        """Test detecting existing remote branch"""
        mock_run.return_value = MagicMock(
            stdout="abc123\trefs/heads/main\n",
            returncode=0,
        )
        assert check_remote_branch_exists("origin", "main") is True

    @patch("subprocess.run")
    def test_branch_does_not_exist(self, mock_run: MagicMock) -> None:
        """Test detecting non-existing remote branch"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        assert check_remote_branch_exists("origin", "nonexistent") is False

    @patch("subprocess.run")
    def test_ls_remote_failure(self, mock_run: MagicMock) -> None:
        """Test handling ls-remote command failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        with pytest.raises(GitError, match="Failed to check remote branch"):
            check_remote_branch_exists("origin", "main")


class TestRunGitSubtreeAdd:
    """Tests for run_git_subtree_add function"""

    @patch("subprocess.run")
    def test_successful_subtree_add(self, mock_run: MagicMock) -> None:
        """Test successful git subtree add"""
        mock_run.return_value = MagicMock(returncode=0)
        run_git_subtree_add("modules/auth", "https://github.com/repo.git", "main")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "subtree" in args
        assert "add" in args
        assert "--prefix=modules/auth" in args
        assert "--squash" in args

    @patch("subprocess.run")
    def test_subtree_add_without_squash(self, mock_run: MagicMock) -> None:
        """Test git subtree add without squash"""
        mock_run.return_value = MagicMock(returncode=0)
        run_git_subtree_add(
            "modules/auth", "https://github.com/repo.git", "main", squash=False
        )
        args = mock_run.call_args[0][0]
        assert "--squash" not in args

    @patch("subprocess.run")
    def test_subtree_add_failure(self, mock_run: MagicMock) -> None:
        """Test handling git subtree add failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        with pytest.raises(GitError, match="Failed to add git subtree"):
            run_git_subtree_add("modules/auth", "https://github.com/repo.git", "main")


class TestRunGitSubtreePull:
    """Tests for run_git_subtree_pull function"""

    @patch("subprocess.run")
    def test_successful_subtree_pull(self, mock_run: MagicMock) -> None:
        """Test successful git subtree pull"""
        mock_run.return_value = MagicMock(stdout="Changes summary", returncode=0)
        output = run_git_subtree_pull(
            "modules/auth", "https://github.com/repo.git", "main"
        )
        assert output == "Changes summary"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_subtree_pull_failure(self, mock_run: MagicMock) -> None:
        """Test handling git subtree pull failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        with pytest.raises(GitError, match="Failed to pull git subtree"):
            run_git_subtree_pull("modules/auth", "https://github.com/repo.git", "main")


class TestRunGitSubtreePush:
    """Tests for run_git_subtree_push function"""

    @patch("subprocess.run")
    def test_successful_subtree_push(self, mock_run: MagicMock) -> None:
        """Test successful git subtree push"""
        mock_run.return_value = MagicMock(returncode=0)
        run_git_subtree_push(
            "modules/auth", "https://github.com/repo.git", "feature/branch"
        )
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "subtree" in args
        assert "push" in args

    @patch("subprocess.run")
    def test_subtree_push_failure(self, mock_run: MagicMock) -> None:
        """Test handling git subtree push failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        with pytest.raises(GitError, match="Failed to push git subtree"):
            run_git_subtree_push(
                "modules/auth", "https://github.com/repo.git", "feature/branch"
            )


class TestGetRemoteUrl:
    """Tests for get_remote_url function"""

    @patch("subprocess.run")
    def test_get_remote_url(self, mock_run: MagicMock) -> None:
        """Test getting remote URL"""
        mock_run.return_value = MagicMock(
            stdout="https://github.com/repo.git\n",
            returncode=0,
        )
        url = get_remote_url()
        assert url == "https://github.com/repo.git"

    @patch("subprocess.run")
    def test_get_remote_url_failure(self, mock_run: MagicMock) -> None:
        """Test handling get remote URL failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="error")
        with pytest.raises(GitError, match="Failed to get remote URL"):
            get_remote_url()


class TestPublicationGitControls:
    """Tests for publication-only executable, environment, and origin gates."""

    @patch("scripts.publish_module.is_working_directory_clean", return_value=True)
    def test_publisher_cleanliness_accepts_clean_worktree(
        self, mock_clean: MagicMock
    ) -> None:
        """Publisher cleanliness checks preserve the clean-worktree route."""
        runner = GitRunner(executable="git", env={}, publication=True)

        assert _has_uncommitted_changes(runner) is False
        mock_clean.assert_called_once_with(
            Path(__file__).resolve().parent.parent.parent,
            runner=runner,
        )

    @patch("scripts.publish_module.is_working_directory_clean", return_value=False)
    def test_publisher_cleanliness_detects_dirty_worktree(
        self, mock_clean: MagicMock
    ) -> None:
        """Publisher cleanliness checks preserve the dirty-worktree route."""
        runner = GitRunner(executable="git", env={}, publication=True)

        assert _has_uncommitted_changes(runner) is True
        mock_clean.assert_called_once()

    @patch(
        "scripts.publish_module.is_working_directory_clean",
        side_effect=GitError("status unavailable"),
    )
    def test_publisher_cleanliness_fails_closed_on_status_error(
        self, mock_clean: MagicMock
    ) -> None:
        """Publisher status errors are treated as dirty/fail-closed."""
        runner = GitRunner(executable="git", env={}, publication=True)

        assert _has_uncommitted_changes(runner) is True
        mock_clean.assert_called_once()

    def test_bootstrap_sanitizes_repository_and_indexed_config_controls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GIT_DIR", "/hostile/repository")
        monkeypatch.setenv("GIT_WORK_TREE", "/hostile/worktree")
        monkeypatch.setenv("GIT_EXEC_PATH", "/hostile/git")
        monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.gitdir")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "/hostile/repository")
        monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/agent.sock")

        runner = build_publication_git_runner(shutil.which("git"))

        assert runner.publication is True
        assert runner.env is not None
        assert "GIT_DIR" not in runner.env
        assert "GIT_WORK_TREE" not in runner.env
        assert "GIT_EXEC_PATH" not in runner.env
        assert "GIT_CONFIG_COUNT" not in runner.env
        assert "GIT_CONFIG_KEY_0" not in runner.env
        assert runner.env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert runner.env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert runner.env["GIT_TERMINAL_PROMPT"] == "0"
        assert runner.env["GIT_LITERAL_PATHSPECS"] == "1"
        assert runner.env["SSH_AUTH_SOCK"] == "/tmp/agent.sock"

    def test_bootstrap_rejects_relative_or_missing_explicit_executable(self) -> None:
        with pytest.raises(GitError, match="absolute"):
            build_publication_git_runner("git")
        with pytest.raises(GitError, match="not executable"):
            build_publication_git_runner("/definitely/missing/git")

    def test_bootstrap_accepts_non_default_valid_git_executable(self) -> None:
        git_path = shutil.which("git")
        assert git_path is not None
        runner = build_publication_git_runner(git_path)
        assert runner.executable == git_path

    @staticmethod
    def _remote_result(mock_run: MagicMock, *, fetch: str, push: str) -> None:
        def result(args: list[str], **_: object) -> MagicMock:
            output = push if "--push" in args else fetch
            return MagicMock(stdout=output, returncode=0)

        mock_run.side_effect = result

    @patch("subprocess.run")
    def test_origin_accepts_effective_https_fetch_and_ssh_push(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        self._remote_result(
            mock_run,
            fetch="https://github.com/Experto-AI/quickscale.git\n",
            push="git@github.com:Experto-AI/quickscale.git\n",
        )
        assert validate_publication_origin(tmp_path) == (
            "https://github.com/Experto-AI/quickscale.git",
            "git@github.com:Experto-AI/quickscale.git",
        )

    @pytest.mark.parametrize("blank", ["", "   \n"])
    @patch("subprocess.run")
    def test_origin_rejects_blank_fetch_or_push(
        self, mock_run: MagicMock, tmp_path: Path, blank: str
    ) -> None:
        self._remote_result(
            mock_run,
            fetch=blank,
            push="https://github.com/Experto-AI/quickscale.git\n",
        )
        with pytest.raises(GitError, match="fetch URL is blank"):
            validate_publication_origin(tmp_path)

    @pytest.mark.parametrize("push", [False, True], ids=["fetch", "push"])
    @pytest.mark.parametrize("padding", [" leading", "trailing "])
    @patch("subprocess.run")
    def test_origin_rejects_surrounding_whitespace_before_allowlist(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
        push: bool,
        padding: str,
    ) -> None:
        """Whitespace-padded effective URLs are not normalized into trust."""
        trusted_url = "https://github.com/Experto-AI/quickscale.git"
        fetch = trusted_url
        push_url = trusted_url
        if push:
            push_url = (
                f"{padding}{trusted_url}"
                if padding.startswith(" ")
                else f"{trusted_url}{padding}"
            )
        else:
            fetch = (
                f"{padding}{trusted_url}"
                if padding.startswith(" ")
                else f"{trusted_url}{padding}"
            )
        self._remote_result(mock_run, fetch=f"{fetch}\n", push=f"{push_url}\n")

        with pytest.raises(
            GitError,
            match=f"Origin {'push' if push else 'fetch'} URL contains surrounding whitespace",
        ):
            validate_publication_origin(tmp_path)

    @patch("subprocess.run")
    def test_origin_rejects_mixed_push_identity(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        self._remote_result(
            mock_run,
            fetch="https://github.com/Experto-AI/quickscale.git\n",
            push="https://github.com/other/project.git\n",
        )
        with pytest.raises(GitError, match="push URL is not"):
            validate_publication_origin(tmp_path)

    @patch("subprocess.run")
    def test_origin_rejects_unset_remote_as_blank(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            128, "git", stderr="error: No such remote 'origin'"
        )
        with pytest.raises(GitError, match="fetch URL is blank or unset"):
            validate_publication_origin(tmp_path)

    @patch("subprocess.run")
    def test_staged_index_nul_parser_handles_special_filenames(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(
            stdout=b'path with spaces\nquotes"\x00', returncode=0
        )
        with pytest.raises(GitError, match="Staged index is not empty"):
            assert_staged_index_empty(tmp_path)

    @patch("subprocess.run")
    def test_staged_index_rejects_malformed_nonempty_stream(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(stdout=b"path-without-nul", returncode=0)
        with pytest.raises(GitError, match="Malformed cached Git path"):
            assert_staged_index_empty(tmp_path)

    @patch("subprocess.run")
    def test_publication_push_asserts_index_before_and_after_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        runner = GitRunner(executable="git", env={}, publication=True)
        mock_run.side_effect = [
            MagicMock(stdout=b"", returncode=0),
            MagicMock(stdout=b"", returncode=0),
            MagicMock(stdout=b"", returncode=0),
        ]
        push_split_branch(
            "splits/auth-module",
            expected_remote_sha="a" * 40,
            path=tmp_path,
            runner=runner,
        )
        commands = [call.args[0][1:] for call in mock_run.call_args_list]
        assert commands[0][:4] == ["diff", "--cached", "--name-only", "-z"]
        assert commands[1][0:2] == [
            "push",
            "--force-with-lease=refs/heads/splits/auth-module:" + "a" * 40,
        ]
        assert commands[2][:4] == ["diff", "--cached", "--name-only", "-z"]

    @patch("subprocess.run")
    def test_publication_push_rejects_index_dirtied_after_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """The post-push assertion is active and remains NUL/path-safe."""
        runner = GitRunner(executable="git", env={}, publication=True)
        mock_run.side_effect = [
            MagicMock(stdout=b"", returncode=0),
            MagicMock(stdout=b"", returncode=0),
            MagicMock(stdout=b"generated\nartifact\0", returncode=0),
        ]
        with pytest.raises(GitError, match="Staged index is not empty"):
            push_split_branch(
                "splits/auth-module",
                expected_remote_sha="a" * 40,
                path=tmp_path,
                runner=runner,
            )
        assert mock_run.call_count == 3


class TestResolveRemoteRef:
    """Tests for resolve_remote_ref function."""

    @patch("subprocess.run")
    def test_resolves_branch_to_commit_sha(self, mock_run: MagicMock) -> None:
        """resolve_remote_ref returns the 40-char SHA from ls-remote."""
        mock_run.return_value = MagicMock(
            stdout="a" * 40 + "\trefs/heads/splits/auth-module\n",
            returncode=0,
        )
        sha = resolve_remote_ref("https://github.com/repo.git", "splits/auth-module")
        assert sha == "a" * 40
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:3] == ["git", "ls-remote", "--heads"]

    @patch("subprocess.run")
    def test_raises_when_branch_not_found(self, mock_run: MagicMock) -> None:
        """resolve_remote_ref raises GitError when the branch is missing."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        with pytest.raises(GitError, match="not found"):
            resolve_remote_ref("https://github.com/repo.git", "splits/missing")

    @patch("subprocess.run")
    def test_raises_on_ls_remote_failure(self, mock_run: MagicMock) -> None:
        """resolve_remote_ref raises GitError on ls-remote command failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="fatal: not found"
        )
        with pytest.raises(GitError, match="Failed to resolve remote ref"):
            resolve_remote_ref("https://github.com/repo.git", "splits/auth-module")

    @patch("subprocess.run")
    def test_raises_on_unexpected_sha_length(self, mock_run: MagicMock) -> None:
        """resolve_remote_ref raises GitError when SHA is not 40 chars."""
        mock_run.return_value = MagicMock(
            stdout="short\trefs/heads/main\n", returncode=0
        )
        with pytest.raises(GitError, match="Unexpected ref format"):
            resolve_remote_ref("https://github.com/repo.git", "main")


# ---------------------------------------------------------------------------
# CR-M5-P3-007: SHA-pinned subtree pull contract verification
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestSubtreePullWithCommitSha:
    """Hermetic integration test proving ``git subtree pull`` accepts a 40-char SHA.

    This test creates a bare remote repo, pushes two commits, then uses
    ``run_git_subtree_add`` with the first commit's SHA and
    ``run_git_subtree_pull`` with the second commit's SHA.  It verifies that
    the subtree content is correctly updated to the second commit.

    This documents and verifies the contract that ``run_git_subtree_pull``
    accepts a fully-spelled hex commit SHA in the *branch* parameter, which
    is how ``_update_single_module`` binds the pull to the exact resolved
    commit (CR-M5-P3-005 / CR-M5-P3-007).

    All tests are branch-default-agnostic (F2.5): they explicitly create
    known branch names instead of relying on the system ``init.defaultBranch``
    setting, and ``test_subtree_sha_proof_is_branch_default_agnostic`` proves
    the SHA-pinned contract holds with non-standard branch names.
    """

    def test_subtree_pull_with_40_char_sha_updates_content(
        self,
        tmp_path: Path,
    ) -> None:
        """git subtree pull with a 40-char SHA fetches the correct commit.

        Branch-default-agnostic: explicitly creates a ``source`` branch in the
        working repo instead of relying on the system default branch name
        (CR-M5-P3-007 / F2.5).
        """
        remote_dir = tmp_path / "remote.git"
        work_dir = tmp_path / "work"
        local_dir = tmp_path / "local"

        # --- Create a bare remote repo ---
        subprocess.run(
            ["git", "init", "--bare", str(remote_dir)],
            check=True,
            capture_output=True,
        )

        # --- Create a working repo to push initial content ---
        subprocess.run(
            ["git", "init", str(work_dir)],
            check=True,
            capture_output=True,
        )
        # Explicitly create a known branch so the test does not depend on the
        # system's ``init.defaultBranch`` setting (F2.5 branch-default-agnostic).
        subprocess.run(
            ["git", "-C", str(work_dir), "checkout", "-b", "source"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # First commit
        (work_dir / "module.txt").write_text("initial content\n")
        subprocess.run(
            ["git", "-C", str(work_dir), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "commit", "-m", "initial commit"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "remote", "add", "origin", str(remote_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(work_dir),
                "push",
                "origin",
                "source:main",
            ],
            check=True,
            capture_output=True,
        )

        # Capture the first commit SHA
        initial_sha_result = subprocess.run(
            ["git", "-C", str(work_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        initial_sha = initial_sha_result.stdout.strip()
        assert len(initial_sha) == 40

        # Second commit
        (work_dir / "module.txt").write_text("updated content\n")
        subprocess.run(
            ["git", "-C", str(work_dir), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "commit", "-m", "second commit"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(work_dir),
                "push",
                "origin",
                "source:main",
            ],
            check=True,
            capture_output=True,
        )

        # Capture the second commit SHA
        second_sha_result = subprocess.run(
            ["git", "-C", str(work_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        second_sha = second_sha_result.stdout.strip()
        assert len(second_sha) == 40
        assert second_sha != initial_sha

        # --- Create the local repo that uses subtree ---
        subprocess.run(
            ["git", "init", str(local_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # Initial commit in local repo (required before subtree add)
        (local_dir / "README.md").write_text("local readme\n")
        subprocess.run(
            ["git", "-C", str(local_dir), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "commit", "-m", "local init"],
            check=True,
            capture_output=True,
        )

        # Subtree add using the first commit SHA
        run_git_subtree_add(
            prefix="modules/test",
            remote=str(remote_dir),
            branch=initial_sha,
            squash=True,
            path=local_dir,
        )

        # Verify initial content was added
        module_file = local_dir / "modules" / "test" / "module.txt"
        assert module_file.exists()
        assert module_file.read_text() == "initial content\n"

        # Subtree pull using the second commit SHA (the contract under test)
        output = run_git_subtree_pull(
            prefix="modules/test",
            remote=str(remote_dir),
            branch=second_sha,
            squash=True,
            path=local_dir,
        )

        # Verify the content was updated to the second commit
        assert module_file.read_text() == "updated content\n"
        # The pull should have produced some output
        assert output  # non-empty stdout

    def test_subtree_add_with_40_char_sha_works(
        self,
        tmp_path: Path,
    ) -> None:
        """git subtree add also accepts a 40-char SHA (companion proof).

        Branch-default-agnostic: explicitly creates a ``source`` branch
        (F2.5 / CR-M5-P3-007).
        """
        remote_dir = tmp_path / "remote.git"
        work_dir = tmp_path / "work"
        local_dir = tmp_path / "local"

        # Create bare remote
        subprocess.run(
            ["git", "init", "--bare", str(remote_dir)],
            check=True,
            capture_output=True,
        )

        # Create working repo with one commit
        subprocess.run(
            ["git", "init", str(work_dir)],
            check=True,
            capture_output=True,
        )
        # Explicitly create a known branch (F2.5 branch-default-agnostic).
        subprocess.run(
            ["git", "-C", str(work_dir), "checkout", "-b", "source"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (work_dir / "module.txt").write_text("sha-pinned content\n")
        subprocess.run(
            ["git", "-C", str(work_dir), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "commit", "-m", "initial commit"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "remote", "add", "origin", str(remote_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "push", "origin", "source:main"],
            check=True,
            capture_output=True,
        )

        sha_result = subprocess.run(
            ["git", "-C", str(work_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        commit_sha = sha_result.stdout.strip()
        assert len(commit_sha) == 40

        # Create local repo
        subprocess.run(
            ["git", "init", str(local_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (local_dir / "README.md").write_text("local\n")
        subprocess.run(
            ["git", "-C", str(local_dir), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )

        # Subtree add using the commit SHA
        run_git_subtree_add(
            prefix="modules/test",
            remote=str(remote_dir),
            branch=commit_sha,
            squash=True,
            path=local_dir,
        )

        module_file = local_dir / "modules" / "test" / "module.txt"
        assert module_file.exists()
        assert module_file.read_text() == "sha-pinned content\n"

    def test_subtree_sha_proof_is_branch_default_agnostic(
        self,
        tmp_path: Path,
    ) -> None:
        """SHA-pinned subtree pull works with a non-standard remote branch name.

        This test uses ``develop`` as the remote branch name (instead of
        ``main``) and a local branch named ``feature`` (instead of ``master``
        or ``main``) to prove the SHA proof does not depend on any specific
        default branch naming convention (F2.5 / CR-M5-P3-007).
        """
        remote_dir = tmp_path / "remote.git"
        work_dir = tmp_path / "work"
        local_dir = tmp_path / "local"

        # Create bare remote
        subprocess.run(
            ["git", "init", "--bare", str(remote_dir)],
            check=True,
            capture_output=True,
        )

        # Create working repo with explicit non-default branch names
        subprocess.run(
            ["git", "init", str(work_dir)],
            check=True,
            capture_output=True,
        )
        # Use a non-standard local branch name
        subprocess.run(
            ["git", "-C", str(work_dir), "checkout", "-b", "feature"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # First commit — push to a non-standard remote branch name
        (work_dir / "module.txt").write_text("v1\n")
        subprocess.run(
            ["git", "-C", str(work_dir), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "commit", "-m", "first"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "remote", "add", "origin", str(remote_dir)],
            check=True,
            capture_output=True,
        )
        # Push local ``feature`` to remote ``develop`` (not ``main``)
        subprocess.run(
            ["git", "-C", str(work_dir), "push", "origin", "feature:develop"],
            check=True,
            capture_output=True,
        )

        initial_sha_result = subprocess.run(
            ["git", "-C", str(work_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        initial_sha = initial_sha_result.stdout.strip()
        assert len(initial_sha) == 40

        # Second commit
        (work_dir / "module.txt").write_text("v2\n")
        subprocess.run(
            ["git", "-C", str(work_dir), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "commit", "-m", "second"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(work_dir), "push", "origin", "feature:develop"],
            check=True,
            capture_output=True,
        )

        second_sha_result = subprocess.run(
            ["git", "-C", str(work_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        second_sha = second_sha_result.stdout.strip()
        assert len(second_sha) == 40
        assert second_sha != initial_sha

        # Create local repo
        subprocess.run(
            ["git", "init", str(local_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (local_dir / "README.md").write_text("local\n")
        subprocess.run(
            ["git", "-C", str(local_dir), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_dir), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )

        # Subtree add with first SHA — remote branch is ``develop``, not ``main``
        run_git_subtree_add(
            prefix="modules/test",
            remote=str(remote_dir),
            branch=initial_sha,
            squash=True,
            path=local_dir,
        )
        module_file = local_dir / "modules" / "test" / "module.txt"
        assert module_file.exists()
        assert module_file.read_text() == "v1\n"

        # Subtree pull with second SHA — proves SHA pin works regardless of
        # the remote branch name
        run_git_subtree_pull(
            prefix="modules/test",
            remote=str(remote_dir),
            branch=second_sha,
            squash=True,
            path=local_dir,
        )
        assert module_file.read_text() == "v2\n"


# ---------------------------------------------------------------------------
# F2.8 — Provenance-aware split-publish helper surface tests
# ---------------------------------------------------------------------------


class TestValidateModuleName:
    """Tests for validate_module_name (CR-M5-P1-001 security boundary)."""

    def test_accepts_simple_slug(self) -> None:
        """validate_module_name accepts plain alphanumeric slugs."""
        validate_module_name("auth")  # must not raise
        validate_module_name("billing")
        validate_module_name("crm")

    def test_accepts_hyphens_and_underscores(self) -> None:
        """validate_module_name accepts slugs with hyphens and underscores."""
        validate_module_name("my-module")
        validate_module_name("my_module")
        validate_module_name("module-v2")
        validate_module_name("a_b-c")

    def test_accepts_leading_digit(self) -> None:
        """validate_module_name accepts slugs starting with a digit."""
        validate_module_name("v2module")
        validate_module_name("3drender")

    def test_rejects_empty(self) -> None:
        """validate_module_name rejects empty string."""
        with pytest.raises(GitError, match="must not be empty"):
            validate_module_name("")

    def test_rejects_path_traversal(self) -> None:
        """validate_module_name rejects path-traversal attempts."""
        with pytest.raises(GitError):
            validate_module_name("..")
        with pytest.raises(GitError):
            validate_module_name("../etc/passwd")
        with pytest.raises(GitError):
            validate_module_name("foo/../../etc/passwd")

    def test_rejects_forward_slash(self) -> None:
        """validate_module_name rejects names with forward slashes."""
        with pytest.raises(GitError):
            validate_module_name("foo/bar")

    def test_rejects_backslash(self) -> None:
        """validate_module_name rejects names with backslashes."""
        with pytest.raises(GitError):
            validate_module_name("foo\\bar")

    def test_rejects_flag_injection(self) -> None:
        """validate_module_name rejects names starting with a hyphen."""
        with pytest.raises(GitError):
            validate_module_name("-flag")
        with pytest.raises(GitError):
            validate_module_name("--force")

    def test_rejects_spaces(self) -> None:
        """validate_module_name rejects names with spaces."""
        with pytest.raises(GitError):
            validate_module_name("my module")
        with pytest.raises(GitError):
            validate_module_name(" leading")

    def test_rejects_shell_metacharacters(self) -> None:
        """validate_module_name rejects shell meta-characters."""
        for bad in ["foo;rm -rf /", "foo$(evil)", "foo`evil`", "foo|bar", "foo&bar"]:
            with pytest.raises(GitError):
                validate_module_name(bad)

    def test_rejects_dot_prefix(self) -> None:
        """validate_module_name rejects names starting with a dot."""
        with pytest.raises(GitError):
            validate_module_name(".hidden")


class TestResolveModulePath:
    """Tests for resolve_module_path (F2.8)."""

    def test_returns_canonical_path(self) -> None:
        """resolve_module_path returns quickscale_modules/<name>."""
        assert resolve_module_path("auth") == "quickscale_modules/auth"
        assert resolve_module_path("billing") == "quickscale_modules/billing"

    def test_rejects_empty_name(self) -> None:
        """resolve_module_path raises GitError for empty module name."""
        with pytest.raises(GitError, match="must not be empty"):
            resolve_module_path("")

    def test_rejects_path_separators(self) -> None:
        """resolve_module_path rejects names containing path separators."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_module_path("foo/bar")
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_module_path("foo\\bar")

    def test_rejects_path_traversal(self) -> None:
        """resolve_module_path rejects .. traversal (CR-M5-P1-001)."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_module_path("..")
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_module_path("../etc/passwd")

    def test_rejects_flag_injection(self) -> None:
        """resolve_module_path rejects names starting with - (CR-M5-P1-001)."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_module_path("--force")

    def test_rejects_spaces(self) -> None:
        """resolve_module_path rejects names with spaces (CR-M5-P1-001)."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_module_path("my module")


class TestResolveSplitBranch:
    """Tests for resolve_split_branch (F2.8)."""

    def test_returns_canonical_branch(self) -> None:
        """resolve_split_branch returns splits/<name>-module."""
        assert resolve_split_branch("auth") == "splits/auth-module"
        assert resolve_split_branch("billing") == "splits/billing-module"

    def test_rejects_empty_name(self) -> None:
        """resolve_split_branch raises GitError for empty module name."""
        with pytest.raises(GitError, match="must not be empty"):
            resolve_split_branch("")

    def test_rejects_path_separators(self) -> None:
        """resolve_split_branch rejects names containing path separators."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_split_branch("foo/bar")

    def test_rejects_path_traversal(self) -> None:
        """resolve_split_branch rejects .. traversal (CR-M5-P1-001)."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_split_branch("..")

    def test_rejects_flag_injection(self) -> None:
        """resolve_split_branch rejects names starting with - (CR-M5-P1-001)."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_split_branch("-flag")

    def test_rejects_spaces(self) -> None:
        """resolve_split_branch rejects names with spaces (CR-M5-P1-001)."""
        with pytest.raises(GitError, match="Invalid module name"):
            resolve_split_branch("my module")


class TestSplitTagHelpers:
    """Focused tests for immutable split-tag and tree helper contracts."""

    def test_resolve_split_tag_uses_canonical_branch_and_version(self) -> None:
        """Split tags are namespaced and use canonical X.Y.Z versions."""
        assert resolve_split_tag("auth", "0.87.0") == "splits/auth-module/0.87.0"

    @pytest.mark.parametrize("version", ["0.87", "0.87.00", " 0.87.0 ", "v0.87.0"])
    def test_resolve_split_tag_rejects_noncanonical_versions(
        self, version: str
    ) -> None:
        """Tag identity must not accept alternate version spellings."""
        with pytest.raises(GitError, match="Invalid canonical version"):
            resolve_split_tag("auth", version)

    @patch("subprocess.run")
    def test_annotated_remote_tag_prefers_peeled_commit(
        self, mock_run: MagicMock
    ) -> None:
        """Annotated tags resolve to the peeled commit, not the tag object."""
        direct_sha = "a" * 40
        peeled_sha = "b" * 40
        mock_run.return_value = MagicMock(
            stdout=(
                f"{direct_sha}\trefs/tags/splits/auth-module/0.87.0\n"
                f"{peeled_sha}\trefs/tags/splits/auth-module/0.87.0^{{}}\n"
            ),
            returncode=0,
        )

        assert resolve_remote_tag("origin", "splits/auth-module/0.87.0") == peeled_sha
        assert mock_run.call_args.args[0] == [
            "git",
            "ls-remote",
            "--tags",
            "--",
            "origin",
            "refs/tags/splits/auth-module/0.87.0",
            "refs/tags/splits/auth-module/0.87.0^{}",
        ]

    @patch("subprocess.run")
    def test_lightweight_remote_tag_uses_direct_commit(
        self, mock_run: MagicMock
    ) -> None:
        """Lightweight tags resolve from their direct ls-remote entry."""
        commit_sha = "c" * 40
        mock_run.return_value = MagicMock(
            stdout=f"{commit_sha}\trefs/tags/splits/auth-module/0.87.0\n",
            returncode=0,
        )

        assert resolve_remote_tag("origin", "splits/auth-module/0.87.0") == commit_sha
        assert check_remote_tag_exists("origin", "splits/auth-module/0.87.0") is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_absent_remote_tag_is_false_or_error(self, mock_run: MagicMock) -> None:
        """Absence is observable as false and is an error for resolution."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)

        assert check_remote_tag_exists("origin", "splits/missing/0.87.0") is False
        with pytest.raises(GitError, match="not found"):
            resolve_remote_tag("origin", "splits/missing/0.87.0")

    @patch("quickscale_core.utils.git_utils.resolve_remote_ref")
    @patch("subprocess.run")
    def test_tag_resolution_does_not_use_remote_ref(
        self, mock_run: MagicMock, mock_remote_ref: MagicMock
    ) -> None:
        """Tag resolution stays separate from branch-only resolve_remote_ref."""
        commit_sha = "d" * 40
        mock_run.return_value = MagicMock(
            stdout=f"{commit_sha}\trefs/tags/splits/auth-module/0.87.0\n",
            returncode=0,
        )

        assert resolve_remote_tag("origin", "splits/auth-module/0.87.0") == commit_sha
        mock_remote_ref.assert_not_called()

    @patch("subprocess.run")
    def test_get_tree_sha_uses_verified_tree_expression(
        self, mock_run: MagicMock
    ) -> None:
        """Tree lookup uses the explicit rev-parse commit peel."""
        tree_sha = "e" * 40
        mock_run.return_value = MagicMock(stdout=f"{tree_sha}\n", returncode=0)

        assert get_tree_sha("f" * 40) == tree_sha
        assert mock_run.call_args.args[0] == [
            "git",
            "rev-parse",
            "--verify",
            f"{'f' * 40}^{{tree}}",
        ]

    @patch("subprocess.run")
    def test_push_tag_uses_one_explicit_non_force_refspec(
        self, mock_run: MagicMock
    ) -> None:
        """Tag pushes cannot sweep tags or force-move an existing tag."""
        mock_run.return_value = MagicMock(returncode=0)

        push_tag("splits/auth-module/0.87.0", remote="upstream")

        assert mock_run.call_args.args[0] == [
            "git",
            "push",
            "--",
            "upstream",
            "refs/tags/splits/auth-module/0.87.0:refs/tags/splits/auth-module/0.87.0",
        ]
        assert all("force" not in arg for arg in mock_run.call_args.args[0])

    @pytest.mark.parametrize(
        "bad_tag",
        [
            "--all",
            "tag*",
            "tag?",
            "tag[",
            "tag:name",
            "tag\nname",
            "refs/tags/tag",
            "tag..other",
            "tag^{}",
            "tag//other",
        ],
    )
    @pytest.mark.parametrize("operation", ["remote", "local", "create", "push"])
    @patch("subprocess.run")
    def test_invalid_tag_values_are_rejected_before_git(
        self, mock_run: MagicMock, operation: str, bad_tag: str
    ) -> None:
        """Tag validation rejects ref syntax and options without spawning Git."""
        with pytest.raises(GitError, match="Invalid tag name"):
            if operation == "remote":
                resolve_remote_tag("origin", bad_tag)
            elif operation == "local":
                get_local_tag_commit(bad_tag)
            elif operation == "create":
                create_annotated_tag(bad_tag, "a" * 40)
            else:
                push_tag(bad_tag)
        mock_run.assert_not_called()

    def test_validate_tag_name_accepts_split_tag(self) -> None:
        """The canonical split-tag namespace remains a valid literal tag."""
        validate_tag_name("splits/auth-module/0.87.0")

    @pytest.mark.parametrize(
        "output, message",
        [
            (
                "b" * 40 + "\trefs/tags/splits/auth-module/0.87.0^{}\n",
                "peeled record without direct",
            ),
            (
                "a" * 40 + "\trefs/tags/splits/auth-module/0.87.0\n"
                "b" * 40 + "\trefs/tags/splits/auth-module/0.87.0\n",
                "duplicate direct",
            ),
            (
                "a" * 40 + "\trefs/tags/splits/auth-module/0.87.0^{}\n"
                "b" * 40 + "\trefs/tags/splits/auth-module/0.87.0^{}\n",
                "duplicate peeled",
            ),
            (
                "a" * 40 + "\trefs/tags/other\n",
                "unknown ref",
            ),
            ("\n", "blank record"),
            ("not-a-record", "Malformed ls-remote"),
        ],
    )
    @patch("subprocess.run")
    def test_remote_tag_parser_rejects_malformed_record_sets(
        self, mock_run: MagicMock, output: str, message: str
    ) -> None:
        """Only one direct plus an optional peeled record is accepted."""
        mock_run.return_value = MagicMock(stdout=output, returncode=0)
        with pytest.raises(GitError, match=message):
            resolve_remote_tag("origin", "splits/auth-module/0.87.0")

    @patch("subprocess.run")
    def test_local_tag_absence_is_confirmed_before_returning_none(
        self, mock_run: MagicMock
    ) -> None:
        """None is returned only for show-ref's explicit absence status."""
        mock_run.return_value = MagicMock(returncode=1, stderr="")

        assert get_local_tag_commit("splits/missing/0.87.0") is None
        assert mock_run.call_args.args[0] == [
            "git",
            "show-ref",
            "--verify",
            "--quiet",
            "refs/tags/splits/missing/0.87.0",
        ]

    @pytest.mark.parametrize(
        "presence, resolution, message",
        [
            (128, None, "Failed to inspect local tag"),
            (
                0,
                MagicMock(returncode=128, stderr="malformed object"),
                "Failed to resolve local tag",
            ),
            (0, MagicMock(returncode=0, stdout="short\n"), "Unexpected tag"),
        ],
    )
    @patch("subprocess.run")
    def test_local_tag_operational_and_malformed_failures_raise(
        self,
        mock_run: MagicMock,
        presence: int,
        resolution: MagicMock | None,
        message: str,
    ) -> None:
        """Operational and malformed-object failures are not treated as absent."""
        presence_result = MagicMock(returncode=presence, stderr="git unavailable")
        if resolution is None:
            mock_run.return_value = presence_result
        else:
            mock_run.side_effect = [presence_result, resolution]

        with pytest.raises(GitError, match=message):
            get_local_tag_commit("splits/auth-module/0.87.0")


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestLocalAnnotatedTagHelpers:
    """Hermetic local-repository tests for annotated-tag idempotence."""

    def _create_repo(self, tmp_path: Path) -> tuple[Path, str]:
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (repo / "module.txt").write_text("initial\n")
        subprocess.run(
            ["git", "-C", str(repo), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return repo, result.stdout.strip()

    def test_create_annotated_tag_is_idempotent_and_rejects_conflict(
        self, tmp_path: Path
    ) -> None:
        """Repeated same-commit tagging is a no-op; a different commit fails."""
        repo, first_sha = self._create_repo(tmp_path)
        tag = "splits/auth-module/0.87.0"

        create_annotated_tag(tag, first_sha, path=repo)
        assert get_local_tag_commit(tag, path=repo) == first_sha
        create_annotated_tag(tag, first_sha, path=repo)

        tag_type = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-t", f"refs/tags/{tag}"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert tag_type.stdout.strip() == "tag"

        (repo / "module.txt").write_text("changed\n")
        subprocess.run(
            ["git", "-C", str(repo), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "changed"],
            check=True,
            capture_output=True,
        )
        second_result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        second_sha = second_result.stdout.strip()

        with pytest.raises(GitError, match=f"{first_sha}.*{second_sha}"):
            create_annotated_tag(tag, second_sha, path=repo)

    def test_push_tag_rejects_conflicting_existing_bare_remote_tag(
        self, tmp_path: Path
    ) -> None:
        """A bare remote tag conflict is rejected without force or mutation."""
        repo, first_sha = self._create_repo(tmp_path)
        remote = tmp_path / "remote.git"
        tag = "splits/auth-module/0.87.0"
        subprocess.run(
            ["git", "init", "--bare", str(remote)], check=True, capture_output=True
        )

        create_annotated_tag(tag, first_sha, path=repo)
        push_tag(tag, remote=str(remote), path=repo)

        (repo / "module.txt").write_text("changed\n")
        subprocess.run(
            ["git", "-C", str(repo), "add", "module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "changed"],
            check=True,
            capture_output=True,
        )
        second_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(repo), "tag", "--force", tag, second_sha],
            check=True,
            capture_output=True,
        )

        with pytest.raises(GitError, match="Failed to push tag"):
            push_tag(tag, remote=str(remote), path=repo)
        assert resolve_remote_tag(str(remote), tag, path=repo) == first_sha


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestSubtreeSplitTreeIdentity:
    """Prove unchanged rejoined subtree splits retain the same tree."""

    def test_unchanged_rejoin_splits_have_equal_trees(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        module_dir = repo / "quickscale_modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.txt").write_text("unchanged\n")
        subprocess.run(
            ["git", "-C", str(repo), "add", "quickscale_modules/auth/module.txt"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )

        first_split = run_git_subtree_split(
            "quickscale_modules/auth",
            "splits/auth-module-first",
            rejoin=True,
            ignore_joins=True,
            path=repo,
        )
        second_split = run_git_subtree_split(
            "quickscale_modules/auth",
            "splits/auth-module-second",
            rejoin=True,
            ignore_joins=True,
            path=repo,
        )

        assert get_tree_sha(first_split, path=repo) == get_tree_sha(
            second_split, path=repo
        )


class TestRunGitSubtreeSplit:
    """Tests for run_git_subtree_split (F2.8)."""

    @patch("subprocess.run")
    def test_successful_split(self, mock_run: MagicMock) -> None:
        """run_git_subtree_split returns the 40-char SHA on success."""
        expected_sha = "a" * 40
        mock_run.return_value = MagicMock(
            stdout=f"{expected_sha}\n",
            returncode=0,
        )
        sha = run_git_subtree_split(
            prefix="quickscale_modules/auth",
            branch="splits/auth-module",
        )
        assert sha == expected_sha
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "subtree" in args
        assert "split" in args
        assert "--prefix=quickscale_modules/auth" in args
        assert "-b" in args
        assert "splits/auth-module" in args
        assert "--rejoin" in args
        assert "--ignore-joins" in args

    @patch("subprocess.run")
    def test_split_without_rejoin(self, mock_run: MagicMock) -> None:
        """run_git_subtree_split omits --rejoin when rejoin=False."""
        mock_run.return_value = MagicMock(
            stdout=f"{'b' * 40}\n",
            returncode=0,
        )
        run_git_subtree_split(
            prefix="quickscale_modules/auth",
            branch="splits/auth-module",
            rejoin=False,
        )
        args = mock_run.call_args[0][0]
        assert "--rejoin" not in args

    @patch("subprocess.run")
    def test_split_failure_raises(self, mock_run: MagicMock) -> None:
        """run_git_subtree_split raises GitError on failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="fatal: not a subtree"
        )
        with pytest.raises(GitError, match="Failed to split git subtree"):
            run_git_subtree_split(
                prefix="quickscale_modules/auth",
                branch="splits/auth-module",
            )

    @patch("subprocess.run")
    def test_split_unexpected_output_raises(self, mock_run: MagicMock) -> None:
        """run_git_subtree_split raises GitError when output is not a 40-char SHA."""
        mock_run.return_value = MagicMock(
            stdout="short-sha\n",
            returncode=0,
        )
        with pytest.raises(GitError, match="Unexpected subtree split output"):
            run_git_subtree_split(
                prefix="quickscale_modules/auth",
                branch="splits/auth-module",
            )


class TestPushSplitBranch:
    """Tests for push_split_branch (F2.8 / SA117 Phase 4)."""

    @patch("subprocess.run")
    def test_push_without_force_by_default(self, mock_run: MagicMock) -> None:
        """push_split_branch does NOT force-push by default (SA117 Phase 4)."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch("splits/auth-module")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "push" in args
        assert "--force" not in args
        assert "--force-with-lease" not in args
        assert "origin" in args
        assert "splits/auth-module" in args

    @patch("subprocess.run")
    def test_push_with_expected_sha(self, mock_run: MagicMock) -> None:
        """push_split_branch uses --force-with-lease when expected_remote_sha given."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch("splits/auth-module", expected_remote_sha="a" * 40)
        args = mock_run.call_args[0][0]
        # --force-with-lease may appear bare or as --force-with-lease=refs/heads/...
        assert any(a.startswith("--force-with-lease") for a in args)
        assert "--force" not in args

    @patch("subprocess.run")
    def test_custom_remote(self, mock_run: MagicMock) -> None:
        """push_split_branch accepts a custom remote name."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch("splits/auth-module", remote="upstream")
        args = mock_run.call_args[0][0]
        assert "upstream" in args

    @patch("subprocess.run")
    def test_push_failure_raises(self, mock_run: MagicMock) -> None:
        """push_split_branch raises GitError on push failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="remote rejected"
        )
        with pytest.raises(GitError, match="Failed to push split branch"):
            push_split_branch("splits/auth-module")


# ---------------------------------------------------------------------------
# Phase 4 (SA117): validate_expected_sha
# ---------------------------------------------------------------------------


class TestValidateExpectedSha:
    """Tests for validate_expected_sha (SA117 Phase 4)."""

    def test_accepts_40_hex(self) -> None:
        """validate_expected_sha accepts a valid 40-char hex SHA."""
        validate_expected_sha("a" * 40)  # must not raise
        validate_expected_sha("abcdef0123456789" + "0" * 24)  # must not raise
        validate_expected_sha("A" * 40)  # uppercase hex is valid

    def test_accepts_absent(self) -> None:
        """validate_expected_sha accepts 'ABSENT'."""
        validate_expected_sha("ABSENT")  # must not raise

    def test_rejects_empty(self) -> None:
        """validate_expected_sha rejects empty string."""
        with pytest.raises(GitError, match="must not be empty"):
            validate_expected_sha("")

    def test_rejects_short_string(self) -> None:
        """validate_expected_sha rejects non-40-char strings."""
        with pytest.raises(GitError, match="must be exactly 40"):
            validate_expected_sha("short")
        with pytest.raises(GitError, match="must be exactly 40"):
            validate_expected_sha("a" * 39)
        with pytest.raises(GitError, match="must be exactly 40"):
            validate_expected_sha("a" * 41)

    def test_rejects_non_hex(self) -> None:
        """validate_expected_sha rejects non-hex characters."""
        with pytest.raises(GitError, match="non-hex"):
            validate_expected_sha("z" + "a" * 39)
        with pytest.raises(GitError, match="non-hex"):
            validate_expected_sha("gggg" + "a" * 36)
        with pytest.raises(GitError, match="non-hex"):
            # Valid hex except for trailing 'x'
            validate_expected_sha("a" * 39 + "x")

    def test_rejects_all_zero(self) -> None:
        """validate_expected_sha rejects all-zero hash."""
        with pytest.raises(GitError, match="all-zero"):
            validate_expected_sha("0" * 40)

    def test_rejects_whitespace_padded(self) -> None:
        """validate_expected_sha rejects whitespace-padded strings."""
        # Space is non-hex, so the 40-char string " aaa...a" fails the hex check
        with pytest.raises(GitError, match="non-hex"):
            validate_expected_sha(" " + "a" * 39)
        # Trailing newline in a 40-char string fails the hex check
        with pytest.raises(GitError, match="non-hex"):
            validate_expected_sha("a" * 39 + "\n")


# ---------------------------------------------------------------------------
# Phase 4 (SA117): push_split_branch with expected_remote_sha
# ---------------------------------------------------------------------------


class TestPushSplitBranchExpectedSha:
    """Tests for push_split_branch with expected_remote_sha (SA117 Phase 4)."""

    @patch("subprocess.run")
    def test_expected_sha_uses_force_with_lease_refspec(
        self, mock_run: MagicMock
    ) -> None:
        """expected_remote_sha generates --force-with-lease=refs/heads/<branch>:<sha>."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch(
            "splits/auth-module",
            expected_remote_sha="a" * 40,
        )
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--force" not in args
        expected_refspec = (
            f"--force-with-lease=refs/heads/splits/auth-module:{'a' * 40}"
        )
        assert expected_refspec in args

    @patch("subprocess.run")
    def test_absent_uses_force_with_lease_plain(self, mock_run: MagicMock) -> None:
        """ABSENT uses --force-with-lease without refspec."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch(
            "splits/auth-module",
            expected_remote_sha="ABSENT",
        )
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--force" not in args
        assert "--force-with-lease" in args
        # Must not have an =refspec suffix
        assert not any(a.startswith("--force-with-lease=") for a in args)

    @patch("subprocess.run")
    def test_bare_force_removed(self, mock_run: MagicMock) -> None:
        """Bare --force is no longer supported (SA117 Phase 4)."""
        mock_run.return_value = MagicMock(returncode=0)
        # push without expected_remote_sha must NOT add --force
        push_split_branch("splits/auth-module")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--force" not in args
        assert "--force-with-lease" not in args

    @patch("subprocess.run")
    def test_empty_expected_sha_raises(self, mock_run: MagicMock) -> None:
        """Empty expected_remote_sha raises GitError."""
        with pytest.raises(GitError, match="must not be empty"):
            push_split_branch("splits/auth-module", expected_remote_sha="")

    @patch("subprocess.run")
    def test_all_zero_expected_sha_raises(self, mock_run: MagicMock) -> None:
        """All-zero expected_remote_sha raises GitError before any push."""
        with pytest.raises(GitError, match="all-zero"):
            push_split_branch("splits/auth-module", expected_remote_sha="0" * 40)
        # subprocess.run should NOT be called — validation must fire first
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# CR-M5-P1-001 / CR-M5-P1-002: Wrapper smoke test for invalid module names
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestPublishModuleWrapperSmoke:
    """Subprocess smoke tests for scripts/publish_module.py (CR-M5-P1-002).

    Proves the wrapper fails closed with a clean operator-facing error
    (no traceback) when given an invalid module name.
    """

    def _repo_root(self) -> Path:
        """Return the repository root (quickscale_core/tests -> repo root)."""
        # test_git_utils.py -> tests/ -> quickscale_core/ -> repo_root
        return Path(__file__).resolve().parent.parent.parent

    def _run_wrapper(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run the publish wrapper as a subprocess."""
        repo_root = self._repo_root()
        script = repo_root / "scripts" / "publish_module.py"
        return subprocess.run(
            # sys.executable, not a bare "python": the latter resolves to
            # whatever interpreter is first on PATH, which may be older than
            # the project floor and fail to parse repo sources at import time.
            [sys.executable, str(script), *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_invalid_module_name_exits_cleanly(self) -> None:
        """Invalid module name exits non-zero with no traceback."""
        # Phase 4 requires --expected-remote-sha even for invalid names
        result = self._run_wrapper("../etc/passwd", "--expected-remote-sha", "a" * 40)
        assert result.returncode != 0
        # Must NOT contain a Python traceback
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout
        # Must contain a clean error message
        combined = result.stdout + result.stderr
        assert "Invalid module name" in combined

    def test_flag_injection_exits_cleanly(self) -> None:
        """Flag-injection module name exits non-zero with no traceback."""
        result = self._run_wrapper("--force")
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_empty_module_name_exits_cleanly(self) -> None:
        """Empty module name (just --) exits non-zero with no traceback."""
        # argparse treats bare '' as a positional arg
        result = self._run_wrapper("")
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_space_in_module_name_exits_cleanly(self) -> None:
        """Module name with spaces exits non-zero with no traceback."""
        result = self._run_wrapper("my module")
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout


# ---------------------------------------------------------------------------
# F2.9a — Release-authoritative source gate tests
# ---------------------------------------------------------------------------


class TestReadVersionFile:
    """Tests for read_version_file (F2.9a)."""

    def test_reads_version_file(self, tmp_path: Path) -> None:
        """read_version_file returns trimmed version string."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("0.86.0\n")
        assert read_version_file(tmp_path) == "0.86.0"

    def test_strips_whitespace_and_cr(self, tmp_path: Path) -> None:
        """read_version_file strips leading/trailing whitespace and CR."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("  0.86.0\r\n  ")
        assert read_version_file(tmp_path) == "0.86.0"

    def test_raises_when_version_file_missing(self, tmp_path: Path) -> None:
        """read_version_file raises GitError when VERSION file does not exist."""
        with pytest.raises(GitError, match="VERSION file not found"):
            read_version_file(tmp_path)

    def test_raises_when_version_file_empty(self, tmp_path: Path) -> None:
        """read_version_file raises GitError when VERSION file is empty."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("")
        with pytest.raises(GitError, match="VERSION file is empty"):
            read_version_file(tmp_path)

    def test_raises_when_version_file_whitespace_only(self, tmp_path: Path) -> None:
        """read_version_file raises GitError when VERSION file has only whitespace."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("   \n  \r\n  ")
        with pytest.raises(GitError, match="VERSION file is empty"):
            read_version_file(tmp_path)


class TestGetTagAtHead:
    """Tests for get_tag_at_head (F2.9a)."""

    @patch("subprocess.run")
    def test_returns_tag_when_head_is_tagged(self, mock_run: MagicMock) -> None:
        """get_tag_at_head returns the tag name when HEAD is tagged."""
        mock_run.return_value = MagicMock(
            stdout="0.86.0\n",
            returncode=0,
        )
        assert get_tag_at_head() == "0.86.0"

    @patch("subprocess.run")
    def test_returns_first_tag_when_multiple_tags(self, mock_run: MagicMock) -> None:
        """get_tag_at_head returns the first tag when multiple tags point at HEAD."""
        mock_run.return_value = MagicMock(
            stdout="0.86.0\nv0.86.0\n",
            returncode=0,
        )
        assert get_tag_at_head() == "0.86.0"

    @patch("subprocess.run")
    def test_returns_none_when_head_is_untagged(self, mock_run: MagicMock) -> None:
        """get_tag_at_head returns None when HEAD has no tag."""
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=0,
        )
        assert get_tag_at_head() is None

    @patch("subprocess.run")
    def test_raises_on_git_failure(self, mock_run: MagicMock) -> None:
        """get_tag_at_head raises GitError on git command failure."""
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="fatal: not a git repository\n",
            returncode=128,
        )
        with pytest.raises(GitError, match="Failed to get tags at HEAD"):
            get_tag_at_head()


class TestGetAllTagsAtHead:
    """Tests for get_all_tags_at_head (F2.9a / CR-F2.9A-002)."""

    @patch("subprocess.run")
    def test_returns_all_tags_when_multiple(self, mock_run: MagicMock) -> None:
        """get_all_tags_at_head returns all tags when multiple point at HEAD."""
        mock_run.return_value = MagicMock(
            stdout="0.86.0\nv0.86.0\nrelease-0.86\n",
            returncode=0,
        )
        tags = get_all_tags_at_head()
        assert tags == ["0.86.0", "v0.86.0", "release-0.86"]

    @patch("subprocess.run")
    def test_returns_single_tag(self, mock_run: MagicMock) -> None:
        """get_all_tags_at_head returns a single-element list for one tag."""
        mock_run.return_value = MagicMock(
            stdout="0.86.0\n",
            returncode=0,
        )
        tags = get_all_tags_at_head()
        assert tags == ["0.86.0"]

    @patch("subprocess.run")
    def test_returns_empty_list_when_untagged(self, mock_run: MagicMock) -> None:
        """get_all_tags_at_head returns empty list when HEAD has no tag."""
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=0,
        )
        tags = get_all_tags_at_head()
        assert tags == []

    @patch("subprocess.run")
    def test_raises_on_git_failure(self, mock_run: MagicMock) -> None:
        """get_all_tags_at_head raises GitError on git command failure."""
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="fatal: not a git repository\n",
            returncode=128,
        )
        with pytest.raises(GitError, match="Failed to get tags at HEAD"):
            get_all_tags_at_head()


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestIsReleaseAuthoritative:
    """Integration tests for is_release_authoritative (F2.9a).

    These tests create hermetic git repos to prove the gate logic against
    real git state.
    """

    def _create_repo_with_version(self, tmp_path: Path, version: str) -> Path:
        """Create a git repo with a VERSION file and return the repo path."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        subprocess.run(
            ["git", "init", str(repo_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (repo_dir / "VERSION").write_text(f"{version}\n")
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", "VERSION"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )
        return repo_dir

    def test_authoritative_when_version_matches_tag(self, tmp_path: Path) -> None:
        """is_release_authoritative returns True when VERSION matches tag at HEAD."""
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "0.86.0"],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is True
        assert version == "0.86.0"
        assert tag == "0.86.0"
        assert reason is None

    def test_authoritative_with_v_prefix_tag(self, tmp_path: Path) -> None:
        """is_release_authoritative accepts tags with lowercase v prefix."""
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "v0.86.0"],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is True
        assert version == "0.86.0"
        assert tag == "v0.86.0"
        assert reason is None

    @pytest.mark.parametrize(
        "bad_tag",
        [
            "V0.86.0",  # uppercase V — not a workflow-authoritative form
            "vv0.86.0",  # multiple lowercase v prefixes — not authoritative
            "vV0.86.0",  # mixed-case prefix — not authoritative
        ],
        ids=["uppercase-V", "double-v", "mixed-vV"],
    )
    def test_not_authoritative_for_non_canonical_tag_shapes(
        self, tmp_path: Path, bad_tag: str
    ) -> None:
        """is_release_authoritative rejects tag shapes outside the workflow authority.

        CR-F2.9A-003: The publish workflow triggers only on ``[0-9]*`` and
        ``v[0-9]*`` tag patterns.  Tags with uppercase ``V``, multiple ``v``
        prefixes, or other non-canonical shapes must not be treated as
        release-authoritative even though their stripped form equals VERSION.
        """
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", bad_tag],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is False
        assert version == "0.86.0"
        assert tag == bad_tag
        assert reason is not None
        assert "does not match" in reason

    def test_not_authoritative_when_untagged(self, tmp_path: Path) -> None:
        """is_release_authoritative returns False when HEAD is untagged."""
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is False
        assert version == "0.86.0"
        assert tag is None
        assert reason is not None
        assert "not tagged" in reason

    def test_not_authoritative_when_version_mismatches_tag(
        self, tmp_path: Path
    ) -> None:
        """is_release_authoritative returns False when VERSION does not match tag."""
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "0.85.0"],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is False
        assert version == "0.86.0"
        assert tag == "0.85.0"
        assert reason is not None
        assert "does not match" in reason

    def test_not_authoritative_when_version_file_missing(self, tmp_path: Path) -> None:
        """is_release_authoritative returns False when VERSION file is missing."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        subprocess.run(
            ["git", "init", str(repo_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (repo_dir / "README.md").write_text("test\n")
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is False
        assert version == ""
        assert tag is None
        assert reason is not None
        assert "VERSION file not found" in reason

    def test_authoritative_when_second_tag_matches(self, tmp_path: Path) -> None:
        """is_release_authoritative succeeds when ANY tag at HEAD matches VERSION.

        CR-F2.9A-002: Previously only checked the first tag.  When multiple
        tags point at HEAD and the first does not match but a later one does,
        the gate must still succeed.
        """
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        # Create a non-matching tag first, then the matching tag
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "release-candidate"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "v0.86.0"],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is True
        assert version == "0.86.0"
        # The matching tag should be returned
        assert tag == "v0.86.0"
        assert reason is None

    def test_not_authoritative_when_no_tag_matches(self, tmp_path: Path) -> None:
        """is_release_authoritative returns False when no tag matches VERSION.

        CR-F2.9A-002: When multiple tags exist but none match VERSION, the
        gate must fail with a clear message.
        """
        repo_dir = self._create_repo_with_version(tmp_path, "0.86.0")
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "release-candidate"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "v0.85.0"],
            check=True,
            capture_output=True,
        )
        is_auth, version, tag, reason = is_release_authoritative(repo_dir)
        assert is_auth is False
        assert version == "0.86.0"
        assert tag is not None  # first tag is returned for diagnostics
        assert reason is not None
        assert "does not match" in reason
        # Should mention multiple tags
        assert "2 tags" in reason


# ---------------------------------------------------------------------------
# F2.9a — Publish wrapper gate integration tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestPublishModuleReleaseAuthoritativeGate:
    """Hermetic integration tests proving the F2.9a gate in scripts/publish_module.py.

    These tests prove:
    1. Mutating publish flows refuse to run when HEAD is untagged
    2. Mutating publish flows refuse to run when VERSION does not match tag
    3. Mutating publish flows succeed when VERSION matches a tag at HEAD
    4. --status remains read-only and does not fail closed on untagged HEAD

    All tests are hermetic: they create a temporary git repo with controlled
    state and run the wrapper script from that location, so they do not depend
    on ambient repo tag state.
    """

    def _setup_hermetic_repo(
        self, tmp_path: Path, version: str, tag: str | None = None
    ) -> Path:
        """Create a hermetic repo structure for wrapper testing.

        Args:
            tmp_path: pytest tmp_path fixture
            version: Version string to write to VERSION file
            tag: Optional tag to create at HEAD (None = untagged)

        Returns:
            Path to the hermetic repo root
        """
        repo_dir = tmp_path / "hermetic_repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(
            ["git", "init", str(repo_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # Create VERSION file
        (repo_dir / "VERSION").write_text(f"{version}\n")

        # Create the authoritative module-discovery seam and its fake inventory.
        _add_authoritative_module_contract(repo_dir)

        # Create scripts/ directory and copy the wrapper script
        scripts_dir = repo_dir / "scripts"
        scripts_dir.mkdir()
        real_repo_root = Path(__file__).resolve().parent.parent.parent
        real_script = real_repo_root / "scripts" / "publish_module.py"
        script_copy = scripts_dir / "publish_module.py"
        script_copy.write_text(real_script.read_text())

        # Create quickscale_core/src structure with symlink to real git_utils
        core_src = repo_dir / "quickscale_core" / "src" / "quickscale_core" / "utils"
        core_src.mkdir(parents=True)
        real_git_utils = (
            real_repo_root
            / "quickscale_core"
            / "src"
            / "quickscale_core"
            / "utils"
            / "git_utils.py"
        )
        # Use symlink to avoid copying the entire package
        (core_src / "git_utils.py").symlink_to(real_git_utils)

        # Create __init__.py files to make it a valid package
        (repo_dir / "quickscale_core" / "__init__.py").write_text("")
        (repo_dir / "quickscale_core" / "src" / "__init__.py").write_text("")
        (
            repo_dir / "quickscale_core" / "src" / "quickscale_core" / "__init__.py"
        ).write_text("")
        (
            repo_dir
            / "quickscale_core"
            / "src"
            / "quickscale_core"
            / "utils"
            / "__init__.py"
        ).write_text("")

        # Commit everything
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", "."],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )

        # Optionally create a tag
        if tag is not None:
            subprocess.run(
                ["git", "-C", str(repo_dir), "tag", tag],
                check=True,
                capture_output=True,
            )

        return repo_dir

    def _run_wrapper(
        self, repo_root: Path, *args: str, timeout: int = 30
    ) -> subprocess.CompletedProcess[str]:
        """Run the publish wrapper as a subprocess in the hermetic repo."""
        script = repo_root / "scripts" / "publish_module.py"
        return subprocess.run(
            # sys.executable, not a bare "python": the latter resolves to
            # whatever interpreter is first on PATH, which may be older than
            # the project floor and fail to parse repo sources at import time.
            [sys.executable, str(script), *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_status_does_not_require_release_authoritative(
        self, tmp_path: Path
    ) -> None:
        """--status does not fail closed when HEAD is untagged.

        Hermetic: creates a temp repo with untagged HEAD.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(repo_dir, "--status", timeout=120)
        combined = result.stdout + result.stderr
        # Should NOT contain the F2.9a gate rejection message
        assert "not release-authoritative" not in combined

    def test_publish_outdated_blocked_in_phase4(self, tmp_path: Path) -> None:
        """--publish-outdated is blocked in SA117 Phase 4 regardless of tag state.

        Hermetic: creates a temp repo with tagged HEAD, but --publish-outdated
        is still rejected before any split/push.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(repo_dir, "--publish-outdated")
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "disabled in SA117 Phase 4" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_single_module_publish_rejects_untagged_head(self, tmp_path: Path) -> None:
        """Single module publish refuses to run when HEAD is untagged.

        Hermetic: creates a temp repo with untagged HEAD.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "a" * 40, timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "not release-authoritative" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_single_module_publish_rejects_version_mismatch(
        self, tmp_path: Path
    ) -> None:
        """Single module publish refuses to run when VERSION does not match tag.

        Hermetic: creates a temp repo with VERSION=0.86.0 but tag=0.85.0.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.85.0")
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "a" * 40, timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "not release-authoritative" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_single_module_publish_rejects_untrusted_origin_before_split(
        self, tmp_path: Path
    ) -> None:
        """The origin gate fails before the first mutating subtree process."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "remote",
                "add",
                "origin",
                "https://evil.invalid/repo.git",
            ],
            check=True,
            capture_output=True,
        )
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "a" * 40, timeout=120
        )
        combined = result.stdout + result.stderr
        assert result.returncode != 0
        assert "Publication origin validation failed" in combined
        assert "Running git subtree split" not in combined
        assert "Traceback" not in combined

    def test_publish_outdated_blocked_regardless_of_version_tag_mismatch(
        self, tmp_path: Path
    ) -> None:
        """--publish-outdated is blocked in SA117 Phase 4 even with version mismatch.

        Hermetic: creates a temp repo with VERSION=0.86.0 but tag=v0.85.0.
        The Phase 4 block fires before any release-authoritative gate check.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="v0.85.0")
        result = self._run_wrapper(repo_dir, "--publish-outdated")
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "disabled in SA117 Phase 4" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    # -----------------------------------------------------------------------
    # F2.9b — Operator diagnostics for split publish mismatches
    # -----------------------------------------------------------------------

    def test_status_reports_untagged_provenance(self, tmp_path: Path) -> None:
        """--status reports NOT-authoritative provenance for untagged HEAD (read-only).

        Hermetic: untagged HEAD.  --status must surface the untagged split
        provenance as a diagnostic without firing the mutating F2.9a gate.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(repo_dir, "--status", timeout=120)
        combined = result.stdout + result.stderr
        # Read-only: --status never fails closed.
        assert result.returncode == 0
        # Diagnostic surfaces the untagged provenance state...
        assert "Release provenance: NOT authoritative" in combined
        assert "not tagged" in combined
        # ...but must NOT emit the mutating F2.9a gate rejection.
        assert "F2.9a gate" not in combined
        assert "not release-authoritative" not in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_status_reports_authoritative_provenance(self, tmp_path: Path) -> None:
        """--status reports authoritative provenance when VERSION matches a tag at HEAD.

        Hermetic: VERSION=0.86.0 tagged v0.86.0.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="v0.86.0")
        result = self._run_wrapper(repo_dir, "--status", timeout=120)
        combined = result.stdout + result.stderr
        assert result.returncode == 0
        assert "Release provenance: authoritative" in combined

    def test_status_reports_unpublished_with_next_action(self, tmp_path: Path) -> None:
        """--status reports unpublished split branches with explicit next-action guidance.

        Hermetic: untagged HEAD with a never-published fake module.  --status
        must report the unpublished split branch and give explicit next-action
        guidance (tag HEAD first) while remaining read-only.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(repo_dir, "--status", timeout=120)
        combined = result.stdout + result.stderr
        assert result.returncode == 0
        # The fake 'auth' module has no published split branch.
        assert "unpublished" in combined
        # Explicit next-action guidance points at tagging first.
        assert "Next action" in combined
        assert "Tag HEAD to match VERSION" in combined


# ---------------------------------------------------------------------------
# Phase 4 (SA117): publish_module.py --expected-remote-sha integration
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class _PublishModuleExpectedRemoteShaBase:
    """Hermetic integration tests for --expected-remote-sha in publish_module.py.

    These tests prove:
    1. --expected-remote-sha is required for single-module publish
    2. Valid --expected-remote-sha passes validation (push itself fails because
       no real remote, but the gate validation succeeds)
    3. Invalid SHA values are rejected before any git operations
    4. --status rejects --expected-remote-sha
    5. --publish-outdated rejects --expected-remote-sha

    All tests are hermetic: they create temporary git repos so they do not
    depend on ambient repo state.
    """

    _hermetic_repo: Path

    def _setup_hermetic_repo(
        self, tmp_path: Path, version: str, tag: str | None = None
    ) -> Path:
        """Create a hermetic repo structure for wrapper testing.

        Args:
            tmp_path: pytest tmp_path fixture
            version: Version string to write to VERSION file
            tag: Optional tag to create at HEAD (None = untagged)

        Returns:
            Path to the hermetic repo root
        """
        repo_dir = tmp_path / "hermetic_repo"
        repo_dir.mkdir()

        subprocess.run(
            ["git", "init", str(repo_dir)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # VERSION file
        (repo_dir / "VERSION").write_text(f"{version}\n")

        # Create the authoritative module-discovery seam and its fake inventory.
        _add_authoritative_module_contract(repo_dir)

        # Copy publish_module.py
        scripts_dir = repo_dir / "scripts"
        scripts_dir.mkdir()
        real_repo_root = Path(__file__).resolve().parent.parent.parent
        real_script = real_repo_root / "scripts" / "publish_module.py"
        (scripts_dir / "publish_module.py").write_text(real_script.read_text())

        # Copy git_utils.py (need to include our new functions)
        core_src = repo_dir / "quickscale_core" / "src" / "quickscale_core" / "utils"
        core_src.mkdir(parents=True)
        real_git_utils = (
            real_repo_root
            / "quickscale_core"
            / "src"
            / "quickscale_core"
            / "utils"
            / "git_utils.py"
        )
        (core_src / "git_utils.py").symlink_to(real_git_utils)

        # Package __init__.py files
        (repo_dir / "quickscale_core" / "__init__.py").write_text("")
        (repo_dir / "quickscale_core" / "src" / "__init__.py").write_text("")
        (
            repo_dir / "quickscale_core" / "src" / "quickscale_core" / "__init__.py"
        ).write_text("")
        (
            repo_dir
            / "quickscale_core"
            / "src"
            / "quickscale_core"
            / "utils"
            / "__init__.py"
        ).write_text("")

        # Commit
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", "."],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )

        if tag is not None:
            subprocess.run(
                ["git", "-C", str(repo_dir), "tag", tag],
                check=True,
                capture_output=True,
            )

        return repo_dir

    def _run_wrapper(
        self, repo_root: Path, *args: str, timeout: int = 30
    ) -> subprocess.CompletedProcess[str]:
        """Run the publish wrapper as a subprocess in the hermetic repo."""
        script = repo_root / "scripts" / "publish_module.py"
        return subprocess.run(
            # sys.executable, not a bare "python": the latter resolves to
            # whatever interpreter is first on PATH, which may be older than
            # the project floor and fail to parse repo sources at import time.
            [sys.executable, str(script), *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # --expected-remote-sha is required
    # ------------------------------------------------------------------

    def test_single_publish_requires_expected_sha(self, tmp_path: Path) -> None:
        """Single-module publish fails when --expected-remote-sha is omitted."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(repo_dir, "auth", timeout=120)
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "expected-remote-sha is required" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout


# ---------------------------------------------------------------------------
# F-006 — real-Git seal lifecycle and trusted-origin proofs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RealPublishRepository:
    """A local working/bare repository pair with captured Git identities."""

    working: Path
    origin: Path
    runner: GitRunner
    first_commit: str
    equal_tree_commit: str
    current_commit: str
    branch: str


def _run_local_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a real Git command against a temporary repository."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _local_git_output(repo: Path, *args: str) -> str:
    """Return trimmed stdout from a real Git command."""
    return _run_local_git(repo, *args).stdout.strip()


def _ref_inventory(repo: Path) -> dict[str, str]:
    """Capture the complete local or bare-repository ref inventory."""
    output = _local_git_output(
        repo,
        "for-each-ref",
        "--format=%(refname)\t%(objectname)",
    )
    return {
        ref: object_id
        for ref, object_id in (
            line.split("\t", 1) for line in output.splitlines() if line
        )
    }


def _assert_ref_inventory_delta(
    before: dict[str, str],
    after: dict[str, str],
    *,
    added: Collection[str] = frozenset(),
    changed: Collection[str] = frozenset(),
) -> None:
    """Assert that a real-Git operation changed only explicitly named refs."""
    assert set(after) - set(before) == added
    assert set(before) - set(after) == set()
    assert {ref for ref in before if before[ref] != after.get(ref)} == changed
    for ref in before:
        if ref not in changed:
            assert after[ref] == before[ref]


def _install_bare_update_hook(origin: Path, body: str) -> Path:
    """Install an executable deterministic receive/update hook in a bare repo."""
    hook = origin / "hooks" / "update"
    hook.write_text(f"#!/bin/sh\nset -eu\n{body}\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


@pytest.fixture
def real_publish_repository(tmp_path: Path) -> _RealPublishRepository:
    """Create controlled local commits and a real publication GitRunner."""
    working = tmp_path / "working"
    origin = tmp_path / "origin.git"
    working.mkdir()
    origin.mkdir()
    subprocess.run(
        ["git", "init", str(working)], check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "init", "--bare", str(origin)],
        check=True,
        capture_output=True,
        text=True,
    )
    _run_local_git(working, "checkout", "-b", "source")
    _run_local_git(working, "config", "user.name", "QuickScale Test")
    _run_local_git(working, "config", "user.email", "quickscale-test@example.invalid")

    module_dir = working / "quickscale_modules" / "auth"
    module_dir.mkdir(parents=True)
    (module_dir / "module.txt").write_text("first tree\n")
    _run_local_git(working, "add", "--", ".")
    _run_local_git(working, "commit", "-m", "first controlled commit")
    first_commit = _local_git_output(working, "rev-parse", "HEAD")

    # An empty commit deliberately keeps the tree identical while changing the
    # commit object.  The following content change supplies the unequal tree.
    _run_local_git(working, "commit", "--allow-empty", "-m", "equal tree commit")
    equal_tree_commit = _local_git_output(working, "rev-parse", "HEAD")
    (module_dir / "module.txt").write_text("current tree\n")
    _run_local_git(working, "add", "--", ".")
    _run_local_git(working, "commit", "-m", "current unequal tree commit")
    current_commit = _local_git_output(working, "rev-parse", "HEAD")

    assert first_commit != equal_tree_commit != current_commit
    assert _local_git_output(working, "rev-parse", f"{first_commit}^{{tree}}") == (
        _local_git_output(working, "rev-parse", f"{equal_tree_commit}^{{tree}}")
    )
    assert _local_git_output(working, "rev-parse", f"{first_commit}^{{tree}}") != (
        _local_git_output(working, "rev-parse", f"{current_commit}^{{tree}}")
    )

    branch = "splits/auth-module"
    _run_local_git(working, "remote", "add", "origin", str(origin))
    _run_local_git(working, "push", "origin", f"HEAD:refs/heads/{branch}")
    git_path = shutil.which("git")
    assert git_path is not None
    return _RealPublishRepository(
        working=working,
        origin=origin,
        runner=build_publication_git_runner(git_path),
        first_commit=first_commit,
        equal_tree_commit=equal_tree_commit,
        current_commit=current_commit,
        branch=branch,
    )


class _RecordingRealGitRunner(GitRunner):
    """Record calls while delegating every operation to a real GitRunner."""

    def __init__(self, delegate: GitRunner) -> None:
        super().__init__(
            executable=delegate.executable,
            env=delegate.env,
            publication=delegate.publication,
        )
        self.delegate = delegate
        self.calls: list[tuple[str, ...]] = []

    def run(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[object]:
        self.calls.append(tuple(args))
        return self.delegate.run(args, **kwargs)


class _MoveOnBranchReadRunner(_RecordingRealGitRunner):
    """Move one real bare ref at a selected branch-read synchronization point."""

    def __init__(
        self,
        delegate: GitRunner,
        *,
        origin: Path,
        branch: str,
        expected: str,
        replacement: str,
    ) -> None:
        super().__init__(delegate)
        self.origin = origin
        self.branch = branch
        self.expected = expected
        self.replacement = replacement
        self.branch_reads = 0

    def run(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[object]:
        if args == ["ls-remote", "--heads", "origin", self.branch]:
            self.branch_reads += 1
            if self.branch_reads == 2:
                self.delegate.run(
                    [
                        "update-ref",
                        f"refs/heads/{self.branch}",
                        self.replacement,
                        self.expected,
                    ],
                    cwd=self.origin,
                    capture_output=True,
                    text=True,
                )
        return super().run(args, **kwargs)


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestPublishModuleSealRealGit:
    """Exercise the production seal helpers against real temporary Git refs."""

    version = "0.88.0"
    previous_version = "0.87.0"

    @staticmethod
    def _patch_repo_root(
        monkeypatch: pytest.MonkeyPatch, repo: _RealPublishRepository
    ) -> None:
        # _seal_module intentionally resolves its repository through the
        # production module root.  Redirecting only this test seam keeps every
        # helper and state-machine operation real while retaining hermeticity.
        monkeypatch.setattr(publish_module, "_REPO_ROOT", repo.working)

    @staticmethod
    def _tag(version: str) -> str:
        return f"splits/auth-module/{version}"

    def test_fixture_captures_real_commit_and_tree_identities(
        self, real_publish_repository: _RealPublishRepository
    ) -> None:
        """The fixture oracle is Git-derived and distinguishes equal/unequal trees."""
        repo = real_publish_repository
        assert len(repo.first_commit) == 40
        assert len(repo.equal_tree_commit) == 40
        assert len(repo.current_commit) == 40
        assert _local_git_output(
            repo.working, "rev-parse", f"{repo.first_commit}^{{tree}}"
        ) == _local_git_output(
            repo.working, "rev-parse", f"{repo.equal_tree_commit}^{{tree}}"
        )
        assert _local_git_output(
            repo.working, "rev-parse", f"{repo.equal_tree_commit}^{{tree}}"
        ) != _local_git_output(
            repo.working, "rev-parse", f"{repo.current_commit}^{{tree}}"
        )

    @pytest.mark.parametrize(
        "annotated", [False, True], ids=["lightweight", "annotated"]
    )
    def test_local_tag_lookup_peels_lightweight_and_annotated_tags(
        self,
        real_publish_repository: _RealPublishRepository,
        annotated: bool,
    ) -> None:
        """Production local lookup returns the commit for either tag object form."""
        repo = real_publish_repository
        tag = self._tag("0.87.1" if annotated else "0.87.2")
        if annotated:
            _run_local_git(
                repo.working,
                "tag",
                "--annotate",
                tag,
                repo.first_commit,
                "--message",
                "annotated fixture tag",
            )
        else:
            _run_local_git(repo.working, "tag", tag, repo.first_commit)

        assert (
            publish_module.get_local_tag_commit(
                tag, path=repo.working, runner=repo.runner
            )
            == repo.first_commit
        )

    def test_create_annotated_tag_is_message_backed_and_peels_to_commit(
        self, real_publish_repository: _RealPublishRepository
    ) -> None:
        """The production creation helper creates one annotated, non-forced tag."""
        repo = real_publish_repository
        tag = self._tag("0.87.3")
        publish_module.create_annotated_tag(
            tag,
            repo.current_commit,
            path=repo.working,
            runner=repo.runner,
        )
        assert _local_git_output(
            repo.working, "cat-file", "-t", f"refs/tags/{tag}"
        ) == ("tag")
        tag_body = _local_git_output(repo.working, "cat-file", "-p", f"refs/tags/{tag}")
        assert "annotated tag" not in tag_body
        assert tag in tag_body
        assert (
            publish_module.get_local_tag_commit(
                tag, path=repo.working, runner=repo.runner
            )
            == repo.current_commit
        )

    def test_push_tag_uses_one_real_explicit_refspec(
        self, real_publish_repository: _RealPublishRepository
    ) -> None:
        """A real push records exactly the one intended tag refspec."""
        repo = real_publish_repository
        tag = self._tag("0.87.4")
        publish_module.create_annotated_tag(
            tag, repo.current_commit, path=repo.working, runner=repo.runner
        )
        recording_runner = _RecordingRealGitRunner(repo.runner)
        publish_module.push_tag(
            tag,
            remote="origin",
            path=repo.working,
            refspec=f"{tag}:refs/tags/{tag}",
            runner=recording_runner,
        )
        assert recording_runner.calls == [
            ("push", "--", "origin", f"refs/tags/{tag}:refs/tags/{tag}")
        ]
        assert (
            _local_git_output(repo.origin, "rev-parse", f"refs/tags/{tag}^{{}}")
            == repo.current_commit
        )

    def test_absent_tag_seal_has_exact_success_ref_delta_and_peeled_identity(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A first seal creates exactly one local and one remote intended tag."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        tag = self._tag(self.version)
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        outcome = publish_module._seal_module("auth", self.version, runner=repo.runner)

        after_work = _ref_inventory(repo.working)
        after_origin = _ref_inventory(repo.origin)
        tag_ref = f"refs/tags/{tag}"
        _assert_ref_inventory_delta(before_work, after_work, added={tag_ref})
        _assert_ref_inventory_delta(before_origin, after_origin, added={tag_ref})
        assert outcome == publish_module.SealOutcome(
            "auth", self.version, repo.branch, tag, repo.current_commit, True
        )
        assert after_work[tag_ref] == after_origin[tag_ref]
        assert (
            _local_git_output(repo.origin, "rev-parse", f"{tag_ref}^{{}}")
            == repo.current_commit
        )

    def test_second_seal_is_idempotent_with_zero_ref_delta(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A verified existing remote tag is a no-mutation second run."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        first = publish_module._seal_module("auth", self.version, runner=repo.runner)
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        second = publish_module._seal_module("auth", self.version, runner=repo.runner)

        assert first.pushed is True
        assert second == publish_module.SealOutcome(
            "auth",
            self.version,
            repo.branch,
            self._tag(self.version),
            repo.current_commit,
            False,
        )
        assert _ref_inventory(repo.working) == before_work
        assert _ref_inventory(repo.origin) == before_origin

    def test_remote_conflicting_tag_fails_without_any_ref_mutation(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A conflicting remote tag is rejected before local creation or push."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        tag = self._tag(self.version)
        publish_module.create_annotated_tag(
            tag, repo.first_commit, path=repo.working, runner=repo.runner
        )
        publish_module.push_tag(
            tag, remote="origin", path=repo.working, runner=repo.runner
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        with pytest.raises(publish_module.SealError, match="conflicts"):
            publish_module._seal_module("auth", self.version, runner=repo.runner)

        assert _ref_inventory(repo.working) == before_work
        assert _ref_inventory(repo.origin) == before_origin
        assert (
            _local_git_output(repo.origin, "rev-parse", f"refs/tags/{tag}^{{}}")
            == repo.first_commit
        )

    def test_conflicting_local_tag_fails_without_remote_mutation(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A conflicting local tag is rejected while preserving both inventories."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        tag = self._tag(self.version)
        publish_module.create_annotated_tag(
            tag, repo.first_commit, path=repo.working, runner=repo.runner
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        with pytest.raises(publish_module.SealError, match="Local tag"):
            publish_module._seal_module("auth", self.version, runner=repo.runner)

        assert _ref_inventory(repo.working) == before_work
        assert _ref_inventory(repo.origin) == before_origin

    def test_equal_previous_tree_reuses_previous_commit(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Equal trees seal the prior commit; the current unequal case is separate."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        _run_local_git(
            repo.origin,
            "update-ref",
            f"refs/heads/{repo.branch}",
            repo.equal_tree_commit,
            repo.current_commit,
        )
        previous_tag = self._tag(self.previous_version)
        target_tag = self._tag(self.version)
        publish_module.create_annotated_tag(
            previous_tag, repo.first_commit, path=repo.working, runner=repo.runner
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        outcome = publish_module._seal_module(
            "auth",
            self.version,
            previous_version=self.previous_version,
            runner=repo.runner,
        )

        assert outcome.commit == repo.first_commit
        assert (
            _local_git_output(repo.origin, "rev-parse", f"refs/tags/{target_tag}^{{}}")
            == repo.first_commit
        )
        _assert_ref_inventory_delta(
            before_work, _ref_inventory(repo.working), added={f"refs/tags/{target_tag}"}
        )
        _assert_ref_inventory_delta(
            before_origin,
            _ref_inventory(repo.origin),
            added={f"refs/tags/{target_tag}"},
        )

    def test_unequal_previous_tree_seals_current_branch_commit(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unequal trees select the captured current remote branch commit."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        previous_tag = self._tag(self.previous_version)
        target_tag = self._tag(self.version)
        publish_module.create_annotated_tag(
            previous_tag, repo.first_commit, path=repo.working, runner=repo.runner
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        outcome = publish_module._seal_module(
            "auth",
            self.version,
            previous_version=self.previous_version,
            runner=repo.runner,
        )

        assert outcome.commit == repo.current_commit
        assert (
            _local_git_output(repo.origin, "rev-parse", f"refs/tags/{target_tag}^{{}}")
            == repo.current_commit
        )
        _assert_ref_inventory_delta(
            before_work, _ref_inventory(repo.working), added={f"refs/tags/{target_tag}"}
        )
        _assert_ref_inventory_delta(
            before_origin,
            _ref_inventory(repo.origin),
            added={f"refs/tags/{target_tag}"},
        )

    def test_immediate_branch_move_stops_before_local_tag_creation(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An event-controlled real runner makes the precondition race deterministic."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        race_runner = _MoveOnBranchReadRunner(
            repo.runner,
            origin=repo.origin,
            branch=repo.branch,
            expected=repo.current_commit,
            replacement=repo.equal_tree_commit,
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        with pytest.raises(
            publish_module.SealError, match="moved before seal mutation"
        ):
            publish_module._seal_module("auth", self.version, runner=race_runner)

        assert race_runner.branch_reads == 2
        assert _ref_inventory(repo.working) == before_work
        _assert_ref_inventory_delta(
            before_origin,
            _ref_inventory(repo.origin),
            changed={f"refs/heads/{repo.branch}"},
        )
        assert f"refs/tags/{self._tag(self.version)}" not in _ref_inventory(repo.origin)

    def test_receive_hook_branch_move_is_detected_after_tag_push_and_cleaned_up(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A receive-time branch race leaves the remote tag but no local cleanup tag."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        tag = self._tag(self.version)
        _install_bare_update_hook(
            repo.origin,
            'if [ "$1" = '
            f"{shlex.quote(f'refs/tags/{tag}')}"
            " ]; then\n"
            f"  git update-ref refs/heads/{shlex.quote(repo.branch)} "
            f"{shlex.quote(repo.equal_tree_commit)} {shlex.quote(repo.current_commit)}\n"
            "fi",
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        with pytest.raises(publish_module.SealError, match="moved after tag push"):
            publish_module._seal_module("auth", self.version, runner=repo.runner)

        _assert_ref_inventory_delta(before_work, _ref_inventory(repo.working))
        _assert_ref_inventory_delta(
            before_origin,
            _ref_inventory(repo.origin),
            added={f"refs/tags/{tag}"},
            changed={f"refs/heads/{repo.branch}"},
        )
        assert f"refs/tags/{tag}" not in _ref_inventory(repo.working)
        assert (
            _local_git_output(repo.origin, "rev-parse", f"refs/tags/{tag}^{{}}")
            == repo.current_commit
        )

    def test_rejected_push_cleans_local_tag_and_preserves_remote_refs(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A rejected tag push is primary and leaves no local created-tag residue."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        tag = self._tag(self.version)
        _install_bare_update_hook(
            repo.origin,
            f'if [ "$1" = {shlex.quote(f"refs/tags/{tag}")} ]; then exit 1; fi',
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        with pytest.raises(publish_module.SealError, match="Tag push failed"):
            publish_module._seal_module("auth", self.version, runner=repo.runner)

        assert _ref_inventory(repo.working) == before_work
        assert _ref_inventory(repo.origin) == before_origin

    def test_rejected_push_and_unavailable_probe_keep_push_error_primary(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A local hook can reject and remove only the temporary origin before probing."""
        repo = real_publish_repository
        self._patch_repo_root(monkeypatch, repo)
        tag = self._tag(self.version)
        offline_origin = Path(f"{repo.origin}.offline")
        _install_bare_update_hook(
            repo.origin,
            'if [ "$1" = '
            f"{shlex.quote(f'refs/tags/{tag}')}"
            " ]; then\n"
            f"  mv -- {shlex.quote(str(repo.origin))} {shlex.quote(str(offline_origin))}\n"
            "  exit 1\n"
            "fi",
        )
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        try:
            with pytest.raises(publish_module.SealError) as excinfo:
                publish_module._seal_module("auth", self.version, runner=repo.runner)
            message = str(excinfo.value)
            assert message.startswith("Tag push failed")
            assert "remote tag probe failed" in message
            assert f"refs/tags/{tag}" not in _ref_inventory(repo.working)
        finally:
            if offline_origin.exists() and not repo.origin.exists():
                shutil.move(str(offline_origin), str(repo.origin))

        assert _ref_inventory(repo.working) == before_work
        assert _ref_inventory(repo.origin) == before_origin


@pytest.mark.skipif(not _git_available(), reason="git not available on PATH")
class TestPublishModuleCliTrustedOrigin:
    """Prove the unmodified CLI gate rejects a local origin before mutation."""

    def test_tagged_local_origin_is_rejected_before_seal_mutation(
        self,
        real_publish_repository: _RealPublishRepository,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI release authority can pass while the trusted-origin gate fails closed."""
        repo = real_publish_repository
        version = "0.89.0"
        (repo.working / "VERSION").write_text(f"{version}\n")
        _run_local_git(repo.working, "add", "--", "VERSION")
        _run_local_git(repo.working, "commit", "-m", "tagged CLI gate fixture")
        _run_local_git(repo.working, "tag", version)
        self_tag = f"refs/tags/{publish_module.resolve_split_tag('auth', version)}"
        before_work = _ref_inventory(repo.working)
        before_origin = _ref_inventory(repo.origin)

        monkeypatch.setattr(publish_module, "_REPO_ROOT", repo.working)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "publish_module.py",
                "auth",
                "--expected-remote-sha",
                "ABSENT",
            ],
        )
        with pytest.raises(SystemExit) as excinfo:
            publish_module.main()

        assert excinfo.value.code == 1
        output = capsys.readouterr().out
        assert "Publication origin validation failed" in output
        assert "trusted github.com/Experto-AI/quickscale repository" in output
        assert _ref_inventory(repo.working) == before_work
        assert _ref_inventory(repo.origin) == before_origin
        assert self_tag not in before_work


class TestPublishModuleExpectedRemoteSha(_PublishModuleExpectedRemoteShaBase):
    """Continue the pre-existing CLI expected-SHA tests after Phase 4 proofs."""

    # ------------------------------------------------------------------
    # Invalid --expected-remote-sha rejection
    # ------------------------------------------------------------------

    def test_rejects_empty_sha(self, tmp_path: Path) -> None:
        """Single-module publish rejects empty --expected-remote-sha."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "", timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "Invalid --expected-remote-sha" in combined
        assert "must not be empty" in combined
        assert "Traceback" not in result.stderr

    def test_rejects_short_sha(self, tmp_path: Path) -> None:
        """Single-module publish rejects short --expected-remote-sha."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "short", timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "Invalid --expected-remote-sha" in combined
        assert "must be exactly 40" in combined
        assert "Traceback" not in result.stderr

    def test_rejects_all_zero_sha(self, tmp_path: Path) -> None:
        """Single-module publish rejects all-zero --expected-remote-sha."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "0" * 40, timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "Invalid --expected-remote-sha" in combined
        assert "all-zero" in combined
        assert "Traceback" not in result.stderr

    def test_rejects_non_hex_sha(self, tmp_path: Path) -> None:
        """Single-module publish rejects non-hex --expected-remote-sha."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "x" + "a" * 39, timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "Invalid --expected-remote-sha" in combined
        assert "non-hex" in combined
        assert "Traceback" not in result.stderr

    # ------------------------------------------------------------------
    # Valid --expected-remote-sha proceeds to gate (untagged = blocked)
    # ------------------------------------------------------------------

    def test_valid_sha_untagged_still_blocked(self, tmp_path: Path) -> None:
        """Valid --expected-remote-sha proceeds past SHA validation but hits gate.

        Hermetic: untagged HEAD with valid --expected-remote-sha.  The SHA
        validation should pass, then the release-authoritative gate should
        block the publish.
        """
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "a" * 40, timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        # Should NOT mention SHA validation failure
        assert "Invalid --expected-remote-sha" not in combined
        # Should mention release-authoritative gate
        assert "not release-authoritative" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_valid_absent_untagged_still_blocked(self, tmp_path: Path) -> None:
        """Valid ABSENT --expected-remote-sha passes SHA validation, hits gate."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(
            repo_dir, "auth", "--expected-remote-sha", "ABSENT", timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "Invalid --expected-remote-sha" not in combined
        assert "not release-authoritative" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    # ------------------------------------------------------------------
    # --status rejects --expected-remote-sha
    # ------------------------------------------------------------------

    def test_status_rejects_expected_sha(self, tmp_path: Path) -> None:
        """--status rejects --expected-remote-sha."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag=None)
        result = self._run_wrapper(
            repo_dir, "--status", "--expected-remote-sha", "a" * 40, timeout=120
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "not supported with --status" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    # ------------------------------------------------------------------
    # --publish-outdated rejects --expected-remote-sha
    # ------------------------------------------------------------------

    def test_publish_outdated_rejected_with_phase4_message(
        self, tmp_path: Path
    ) -> None:
        """--publish-outdated is blocked in SA117 Phase 4 (even with --expected-remote-sha)."""
        repo_dir = self._setup_hermetic_repo(tmp_path, "0.86.0", tag="0.86.0")
        result = self._run_wrapper(
            repo_dir,
            "--publish-outdated",
            "--expected-remote-sha",
            "a" * 40,
            timeout=120,
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "disabled in SA117 Phase 4" in combined
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout
