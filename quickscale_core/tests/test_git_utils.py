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
    push_split_branch,
    resolve_module_path,
    resolve_remote_ref,
    resolve_split_branch,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
    run_git_subtree_split,
    validate_module_name,
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
    """Tests for push_split_branch (F2.8)."""

    @patch("subprocess.run")
    def test_force_push_by_default(self, mock_run: MagicMock) -> None:
        """push_split_branch force-pushes by default."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch("splits/auth-module")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "push" in args
        assert "--force" in args
        assert "origin" in args
        assert "splits/auth-module" in args

    @patch("subprocess.run")
    def test_non_force_push(self, mock_run: MagicMock) -> None:
        """push_split_branch omits --force when force=False."""
        mock_run.return_value = MagicMock(returncode=0)
        push_split_branch("splits/auth-module", force=False)
        args = mock_run.call_args[0][0]
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
            ["python", str(script), *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_invalid_module_name_exits_cleanly(self) -> None:
        """Invalid module name exits non-zero with no traceback."""
        result = self._run_wrapper("../etc/passwd")
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
