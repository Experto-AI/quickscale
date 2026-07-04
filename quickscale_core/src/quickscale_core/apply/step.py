"""ApplyStep dataclass and the ordered registry of apply steps.

Each :class:`ApplyStep` captures the stable identity and descriptive
metadata for one step of the ``quickscale apply`` command.  The registry
:data:`APPLY_STEPS` enumerates all 16 steps in their canonical execution
order.

The ``step_id`` for each step is the stable identifier used in the
recovery ledger and roadmap tracking.  For steps that carry a
``failed_step`` abort label in the apply command implementation, the
``step_id`` is set to that verbatim label string so that existing
recovery sentinels remain valid after any future refactor.

No imports from ``quickscale_cli`` are permitted here; this module is
pure ``quickscale_core`` domain code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplyStep:
    """Immutable descriptor for a single step in the apply pipeline.

    Attributes:
        order: 1-based position in the canonical execution order (1..16).
        step_id: Stable identifier for this step.  For the 14 steps that
            carry a ``failed_step`` abort label in the apply implementation,
            this equals that verbatim label string so recovery sentinels
            remain valid.  For steps without a label (steps 11, 16) the
            descriptive name is used.
        failed_step_label: The verbatim ``failed_step`` string used by the
            apply command when aborting on this step, or ``None`` for steps
            that do not abort with a labelled sentinel (best-effort or
            informational steps).  Currently None for steps 11 and 16.
        apply_action: Short stable descriptor of what the step does.
        resume: Compensating/resume descriptor.  There is no rollback today;
            all irreversible steps use ``"idempotent-rerun"`` (presence-gated
            re-execution).  Finalization and display steps use ``"finalize"``
            and ``"display"`` respectively.
        reversible: ``False`` for all steps; the full apply pipeline has no
            rollback capability.  Steps 1-14 are tagged explicitly
            irreversible (cross-system side effects); steps 15-16 are
            finalization/display steps.

    """

    order: int
    step_id: str
    failed_step_label: str | None
    apply_action: str
    resume: str
    reversible: bool


#: Ordered registry of all 16 apply steps.
#:
#: The ordering matches ``_execute_apply_steps_locked`` in
#: ``quickscale_cli.commands.apply_command``.  Step IDs and
#: ``failed_step_label`` values are derived verbatim from that
#: implementation to preserve label stability across refactors.
APPLY_STEPS: tuple[ApplyStep, ...] = (
    ApplyStep(
        order=1,
        step_id="module embedding",
        failed_step_label="module embedding",
        apply_action="module embedding",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=2,
        step_id="post-embed state snapshot",
        failed_step_label="post-embed state snapshot",
        apply_action="post-embed state snapshot",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=3,
        step_id="managed module wiring generation",
        failed_step_label="managed module wiring generation",
        apply_action="managed module wiring generation",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=4,
        step_id="capture managed file hashes",
        failed_step_label="capture managed file hashes",
        apply_action="capture managed file hashes",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=5,
        step_id="backups gitignore hardening",
        failed_step_label="backups gitignore hardening",
        apply_action="backups gitignore hardening",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=6,
        step_id="notifications env example sync",
        failed_step_label="notifications env example sync",
        apply_action="notifications env example sync",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=7,
        step_id="analytics env example sync",
        failed_step_label="analytics env example sync",
        apply_action="analytics env example sync",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=8,
        step_id="billing env example sync",
        failed_step_label="billing env example sync",
        apply_action="billing env example sync",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=9,
        step_id="module dependency sync",
        failed_step_label="module dependency sync",
        apply_action="module dependency sync",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=10,
        step_id="post-generation dependency and migration setup",
        failed_step_label="post-generation dependency and migration setup",
        apply_action="post-generation dependency and migration setup",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=11,
        step_id="apply mutable config",
        failed_step_label=None,
        apply_action="apply mutable config",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=12,
        step_id="docker startup",
        failed_step_label="docker startup",
        apply_action="docker startup",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=13,
        step_id="database migrations",
        failed_step_label="database migrations",
        apply_action="database migrations",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=14,
        step_id="railway deploy",
        failed_step_label="railway deploy",
        apply_action="railway deploy",
        resume="idempotent-rerun",
        reversible=False,
    ),
    ApplyStep(
        order=15,
        step_id="authoritative state persistence",
        failed_step_label="authoritative state persistence",
        apply_action="finalize apply state",
        resume="finalize",
        reversible=False,
    ),
    ApplyStep(
        order=16,
        step_id="display next steps",
        failed_step_label=None,
        apply_action="display next steps",
        resume="display",
        reversible=False,
    ),
)


def step_by_id(step_id: str) -> ApplyStep:
    """Return the :class:`ApplyStep` with the given ``step_id``.

    Args:
        step_id: The stable step identifier to look up.

    Returns:
        The matching :class:`ApplyStep`.

    Raises:
        KeyError: If no step with that ``step_id`` exists in the registry.

    """
    for step in APPLY_STEPS:
        if step.step_id == step_id:
            return step
    raise KeyError(f"No ApplyStep with step_id={step_id!r}")


__all__ = [
    "APPLY_STEPS",
    "ApplyStep",
    "step_by_id",
]
