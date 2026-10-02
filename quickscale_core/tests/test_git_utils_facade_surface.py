"""Conformance gate: the split git utility surface keeps its imports.

SA231 moved the implementation into sibling ``git_*`` modules. Every name
the former ``quickscale_core.utils.git_utils`` module exposed at import time
must remain importable from the same module path; production callers use
explicit ``from ... import`` lists and the publication wrapper smoke fixture
symlinks this module plus its siblings.
"""

from unittest.mock import MagicMock, patch

import quickscale_core.utils.git_utils as git_utils
from quickscale_core.utils import (
    git_errors,
    git_naming,
    git_publish,
    git_repo,
    git_runner,
    git_subtree,
    git_tags,
)

EXPECTED_MODULE_SURFACE = frozenset(
    {
        "GitError",
        "GitRunner",
        "assert_staged_index_empty",
        "build_publication_git_runner",
        "check_remote_branch_exists",
        "check_remote_tag_exists",
        "create_annotated_tag",
        "get_all_tags_at_head",
        "get_local_tag_commit",
        "get_remote_url",
        "get_tag_at_head",
        "get_tree_sha",
        "is_git_repo",
        "is_release_authoritative",
        "is_working_directory_clean",
        "push_split_branch",
        "push_tag",
        "read_version_file",
        "resolve_module_path",
        "resolve_remote_ref",
        "resolve_remote_tag",
        "resolve_split_branch",
        "resolve_split_tag",
        "run_git_subtree_add",
        "run_git_subtree_pull",
        "run_git_subtree_push",
        "run_git_subtree_split",
        "validate_expected_sha",
        "validate_module_name",
        "validate_publication_local_config",
        "validate_publication_origin",
        "validate_tag_name",
    }
)


def test_facade_preserves_former_module_surface() -> None:
    """Every name the former module exposed stays importable from git_utils."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(dir(git_utils)))
    assert not missing, f"facade dropped former module names: {missing}"


def test_facade_declares_every_former_public_name() -> None:
    """Every former public name stays in ``__all__`` for wildcard consumers."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(git_utils.__all__))
    assert not missing, f"facade __all__ dropped former public names: {missing}"


def test_facade_reexports_the_original_objects() -> None:
    """Re-exported names stay identical to their defining objects."""
    assert git_utils.GitError is git_errors.GitError
    assert git_utils.GitRunner is git_runner.GitRunner
    assert git_utils.validate_publication_origin is git_repo.validate_publication_origin
    assert git_utils.run_git_subtree_split is git_subtree.run_git_subtree_split
    assert git_utils.validate_tag_name is git_tags.validate_tag_name
    assert git_utils.resolve_module_path is git_naming.resolve_module_path
    assert git_utils.push_split_branch is git_publish.push_split_branch
    assert git_utils.is_release_authoritative is git_publish.is_release_authoritative
    assert (
        git_utils.build_publication_git_runner
        is git_runner.build_publication_git_runner
    )


def test_tag_lookup_stays_tag_only_at_the_split_seam() -> None:
    """Tag resolution must query tags only, never the branch resolver.

    The former same-module negative mock can no longer observe the split
    ``git_repo.resolve_remote_ref`` implementation, so this guard pins the
    tag-only query at the new seam: the branch resolver is not called and
    the subprocess query carries ``--tags`` without ``--heads``.
    """
    tag_sha = "a" * 40
    completed = MagicMock(
        returncode=0,
        stdout=f"{tag_sha}\trefs/tags/v1.0.0\n",
        stderr="",
    )
    with (
        patch.object(git_repo, "resolve_remote_ref") as branch_lookup,
        patch("subprocess.run", return_value=completed) as run,
    ):
        assert git_tags.resolve_remote_tag("origin", "v1.0.0") == tag_sha

    branch_lookup.assert_not_called()
    argv = run.call_args.args[0]
    assert "--tags" in argv
    assert "--heads" not in argv
