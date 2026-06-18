"""Unit tests for git utilities."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.utils.git_utils import (
    GitError,
    check_remote_branch_exists,
    get_remote_url,
    is_git_repo,
    is_working_directory_clean,
    resolve_remote_ref,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
)


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
        mock_run.return_value = MagicMock(stdout="M  file.py\n", returncode=0)
        assert is_working_directory_clean() is False

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
