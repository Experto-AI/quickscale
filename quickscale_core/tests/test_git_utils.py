"""Unit tests for git utilities."""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.publish_module import _has_uncommitted_changes

from quickscale_core.utils.git_utils import (
    GitError,
    GitRunner,
    assert_staged_index_empty,
    build_publication_git_runner,
    check_remote_branch_exists,
    get_all_tags_at_head,
    get_remote_url,
    get_tag_at_head,
    is_git_repo,
    is_release_authoritative,
    is_working_directory_clean,
    push_split_branch,
    read_version_file,
    resolve_module_path,
    resolve_remote_ref,
    resolve_split_branch,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
    run_git_subtree_split,
    validate_publication_origin,
    validate_expected_sha,
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

        # Create minimal quickscale_modules/ structure with a fake module
        modules_dir = repo_dir / "quickscale_modules" / "auth"
        modules_dir.mkdir(parents=True)
        (modules_dir / "__init__.py").write_text("# fake module\n")

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
class TestPublishModuleExpectedRemoteSha:
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

        # quickscale_modules/ with a fake module
        modules_dir = repo_dir / "quickscale_modules" / "auth"
        modules_dir.mkdir(parents=True)
        (modules_dir / "__init__.py").write_text("# fake\n")

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
        assert "expected-remote-sha is required" in combined
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
