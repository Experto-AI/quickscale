"""Git error type shared by the split git utility surface.

Re-exported from ``quickscale_core.utils.git_utils`` so every caller keeps
importing the same class object it always did.
"""


class GitError(Exception):
    """Raised when a git operation fails."""

    pass
