"""Git utilities for module management via git subtree operations.

The implementation lives in focused sibling ``git_*`` modules; this module
stays the import path every caller uses and re-exports its full former
surface, so all existing ``quickscale_core.utils.git_utils`` imports keep
working.
"""

from __future__ import annotations

from quickscale_core.utils.git_errors import GitError
from quickscale_core.utils.git_naming import (
    resolve_module_path,
    resolve_split_branch,
    resolve_split_tag,
    validate_module_name,
)
from quickscale_core.utils.git_publish import (
    get_all_tags_at_head,
    get_tag_at_head,
    is_release_authoritative,
    push_split_branch,
    read_version_file,
    validate_expected_sha,
)
from quickscale_core.utils.git_repo import (
    check_remote_branch_exists,
    get_remote_url,
    is_git_repo,
    is_working_directory_clean,
    resolve_remote_ref,
    validate_publication_origin,
)
from quickscale_core.utils.git_runner import (
    GitRunner,
    assert_staged_index_empty,
    build_publication_git_runner,
    validate_publication_local_config,
)
from quickscale_core.utils.git_subtree import (
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
    run_git_subtree_split,
)
from quickscale_core.utils.git_tags import (
    check_remote_tag_exists,
    create_annotated_tag,
    get_local_tag_commit,
    get_tree_sha,
    push_tag,
    resolve_remote_tag,
    validate_tag_name,
)

__all__ = [
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
]
