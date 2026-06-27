"""Step bodies for module embedding and post-embed state snapshot.

Step 1 (module embedding) and step 2 (post-embed state snapshot) are
extracted here.  These steps are closely coupled: the state snapshot
consumes the result of module embedding.

Phase 2 extracts the orchestration bodies.  CLI-level embed/commit
operations are supplied as injected callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Step 1: module embedding
# ---------------------------------------------------------------------------


@dataclass
class EmbedModulesResult:
    """Result of embedding one or more modules.

    This mirrors the CLI-level EmbedModulesResult so that callers can
    convert between the two forms.  Phase 2 keeps both definitions; a
    future phase may consolidate them.
    """

    success: bool
    embedded_modules: list[str] = field(default_factory=list)
    failed_module: str | None = None
    provenance_payloads: dict[str, Any] | None = None
    commit_sha_map: dict[str, str] = field(default_factory=dict)


def step_embed_modules(
    ctx: StepContext,
    *,
    modules_to_embed: list[str],
    no_modules: bool,
    embed_one_module: Callable[..., bool],
    commit_changes: Callable[..., bool],
    is_working_directory_clean_fn: Callable[..., bool],
    provenance_sink: list[Any] | None = None,
) -> StepOutcome:
    """Step 1: Embed modules into the generated project with fail-fast semantics.

    Iterates over *modules_to_embed*, calling *embed_one_module* for each,
    then *commit_changes* after each successful embed.  On failure the
    function returns an unsuccessful :class:`StepOutcome` carrying the
    ``failed_step_label`` for module embedding.

    The caller (CLI adapter) is responsible for providing the actual embed
    and commit implementations.

    Args:
        ctx: Core-safe step context.
        modules_to_embed: Module names to embed in this pass.
        no_modules: Flag to skip embedding entirely.
        embed_one_module: Callable that embeds a single module and returns
            ``True`` on success.
        commit_changes: Callable that creates a git checkpoint commit and
            returns ``True`` on success.
        is_working_directory_clean_fn: Callable that checks whether the
            working directory is clean.
        provenance_sink: Optional list for capturing per-module provenance
            payloads.

    Returns:
        A :class:`StepOutcome`.  On success, ``StepOutcome.success`` is
        ``True`` and *ctx.embedded_modules* has been populated.
    """
    embedded_modules: list[str] = []
    provenance_payloads: dict[str, Any] = {}

    if no_modules or not modules_to_embed:
        return StepOutcome(
            success=True,
            message="No modules to embed",
        )

    skip_auth_migration_check = ctx.existing_state is None
    output_path = ctx.output_path

    for module_name in modules_to_embed:
        module_provenance: list[Any] = []
        if not embed_one_module(
            output_path,
            module_name,
            skip_auth_migration_check=skip_auth_migration_check,
            provenance_sink=module_provenance,
        ):
            if not is_working_directory_clean_fn(output_path):
                if not commit_changes(
                    output_path,
                    f"Partial module: {module_name} (incomplete)",
                ):
                    ctx.embed_commit_failure = True
                    ctx.embedded_modules = embedded_modules
                    ctx.provenance_payloads = provenance_payloads
                    return StepOutcome(
                        success=False,
                        message=(
                            f"Cannot continue: QuickScale could not create "
                            f"the partial module checkpoint commit after "
                            f"embedding {module_name} failed."
                        ),
                        failed_step_label="module embedding",
                    )
            ctx.embed_failed_module = module_name
            ctx.embedded_modules = embedded_modules
            ctx.provenance_payloads = provenance_payloads
            return StepOutcome(
                success=False,
                message=f"Module embedding failed for required module: {module_name}",
                failed_step_label="module embedding",
            )

        if not commit_changes(output_path, f"Add module: {module_name}"):
            ctx.embed_commit_failure = True
            ctx.embedded_modules = embedded_modules
            ctx.provenance_payloads = provenance_payloads
            return StepOutcome(
                success=False,
                message=(
                    f"Cannot continue: QuickScale could not create "
                    f"the checkpoint commit for embedded module "
                    f"'{module_name}'."
                ),
                failed_step_label="module embedding",
            )

        embedded_modules.append(module_name)
        if module_provenance:
            provenance_payloads[module_name] = module_provenance[0]

    ctx.embedded_modules = embedded_modules
    ctx.provenance_payloads = provenance_payloads

    return StepOutcome(
        success=True,
        message=f"Embedded {len(embedded_modules)} module(s): {', '.join(embedded_modules)}",
    )


# ---------------------------------------------------------------------------
# Step 2: post-embed state snapshot
# ---------------------------------------------------------------------------


@dataclass
class GitIndexSnapshot:
    """Captured git index tree id for recovery checkpointing."""

    tree_id: str


def step_post_embed_snapshot(
    ctx: StepContext,
    *,
    build_state_snapshot: Callable[..., Any],
    capture_git_index: Callable[..., GitIndexSnapshot | None],
) -> StepOutcome:
    """Step 2: Build the post-embed state snapshot and capture git index.

    Uses injected callbacks to build the state snapshot from the current
    context and to capture the git index tree id.  Both are required for
    safe recovery state persistence on subsequent step failure.

    Args:
        ctx: Core-safe step context.  ``ctx.embedded_modules`` must have
            been populated by :func:`step_embed_modules`.
        build_state_snapshot: Callable that returns a
            ``QuickScaleState`` for the post-embed snapshot.
        capture_git_index: Callable that returns a
            :class:`GitIndexSnapshot` with the current git tree id, or
            ``None`` on failure.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"post-embed state snapshot"`` on failure.
    """
    try:
        post_embed_state = build_state_snapshot()
    except Exception as error:
        return StepOutcome(
            success=False,
            message=(
                "QuickScale could not compute the post-embed state required "
                f"for safe apply recovery: {error}"
            ),
            failed_step_label="post-embed state snapshot",
        )

    checkpoint = capture_git_index()
    if checkpoint is None:
        return StepOutcome(
            success=False,
            message=(
                "QuickScale could not capture the git index tree id "
                "after module embedding for apply recovery state."
            ),
            failed_step_label="post-embed state snapshot",
        )

    ctx.state_snapshot = post_embed_state
    ctx.checkpoint_tree_id = checkpoint.tree_id

    return StepOutcome(
        success=True,
        message="Post-embed state snapshot and git index checkpoint captured",
    )


__all__ = [
    "EmbedModulesResult",
    "GitIndexSnapshot",
    "step_embed_modules",
    "step_post_embed_snapshot",
]
