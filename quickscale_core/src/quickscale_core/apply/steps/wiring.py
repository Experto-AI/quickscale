"""Step bodies for managed wiring generation and file hash capture.

Step 3 (managed module wiring generation) and step 4 (capture managed file
hashes) are extracted here.  Both steps operate on the post-embed project
state.
"""

from __future__ import annotations

from typing import Callable

from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Step 3: managed module wiring generation
# ---------------------------------------------------------------------------


def step_regenerate_wiring(
    ctx: StepContext,
    *,
    embedded_modules: list[str],
    regenerate_wiring_fn: Callable[..., tuple[bool, str]],
) -> StepOutcome:
    """Step 3: Regenerate managed module wiring files after embed/config changes.

    Delegates the actual rendering to *regenerate_wiring_fn*, which should
    return a ``(success, message)`` tuple.

    Args:
        ctx: Core-safe step context carrying ``qs_config``, ``existing_state``,
            ``delta``, and ``output_path``.
        embedded_modules: Modules embedded in this apply pass.
        regenerate_wiring_fn: Callable that renders managed wiring files and
            returns ``(success, message)``.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"managed module wiring generation"`` on failure.
    """
    if ctx.reporter:
        ctx.reporter("Regenerating managed module wiring...")

    success, message = regenerate_wiring_fn(
        ctx.output_path,
        module_names=embedded_modules,
        qs_config=ctx.qs_config,
        existing_state=ctx.existing_state,
        delta=ctx.delta,
    )

    if not success:
        return StepOutcome(
            success=False,
            message=message or "Managed wiring regeneration failed",
            failed_step_label="managed module wiring generation",
        )

    if ctx.reporter:
        ctx.reporter("Managed module wiring regenerated", ok=True)

    return StepOutcome(success=True, message="Managed module wiring regenerated")


# ---------------------------------------------------------------------------
# Step 4: capture managed file hashes
# ---------------------------------------------------------------------------


def step_capture_hashes(
    ctx: StepContext,
    *,
    compute_file_hashes_fn: Callable[..., dict[str, str]],
    resolve_managed_wiring_paths_fn: Callable[..., list[str]],
    record_hash_fn: Callable[..., None],
) -> StepOutcome:
    """Step 4: Capture SHA-256 hashes of managed wiring files.

    Hash capture runs over files the apply pipeline itself just wrote.
    An ``OSError`` during resolution or hashing is a genuine system-level
    problem (disk full, permissions, filesystem corruption) and aborts the
    step with ``success=False``.

    Args:
        ctx: Core-safe step context.
        compute_file_hashes_fn: Callable that computes file hashes for
            a list of repo-relative paths and returns
            ``{path: sha256_hex_digest}``.
        resolve_managed_wiring_paths_fn: Callable that returns the list
            of repo-relative managed wiring paths to track.
        record_hash_fn: Callable that stores a hash record in the
            state object (``ctx.state_snapshot``).

    Returns:
        :class:`StepOutcome` with ``success=False`` and
        ``failed_step_label="capture managed file hashes"`` on
        ``OSError``.
    """
    try:
        managed_paths = resolve_managed_wiring_paths_fn()
        if not managed_paths:
            return StepOutcome(success=True, message="No managed wiring paths to track")

        hashes = compute_file_hashes_fn(ctx.output_path, managed_paths)
    except OSError as error:
        if ctx.reporter:
            ctx.reporter(f"⚠️  Failed to capture managed file hashes: {error}", ok=False)
        return StepOutcome(
            success=False,
            message=f"Failed to capture managed file hashes: {error}",
            failed_step_label="capture managed file hashes",
        )

    for path_str, digest in hashes.items():
        record_hash_fn(path_str, digest)

    if hashes and ctx.reporter:
        ctx.reporter(f"Tracked managed file hashes for {len(hashes)} file(s)", ok=True)

    return StepOutcome(
        success=True,
        message=f"Captured hashes for {len(hashes)} managed file(s)",
    )


__all__ = [
    "step_capture_hashes",
    "step_regenerate_wiring",
]
