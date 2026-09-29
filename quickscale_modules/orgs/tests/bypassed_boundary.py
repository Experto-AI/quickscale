"""Negative control for the boundary-wiring system check.

The entry point never routes a stage, while an unreachable helper keeps every
coordinator call.  The check follows the executing path, so this module must
fail it.  It is not a pytest module: the file name does not match ``test_*.py``.
"""

from __future__ import annotations

from quickscale_modules_orgs.removal import (
    RemovalAction,
    RemovalBoundary,
    RemovalCoordinator,
)


class BypassingPurgeBoundary:
    """A boundary whose entry point never reaches the coordinator."""

    def handle(self) -> None:
        """Bypass the shared coordinator entirely."""


class DeadBranchPurgeBoundary:
    """A boundary whose coordinator calls sit behind a dead branch."""

    def handle(self) -> None:
        """Call the coordinator only under a constant-false condition."""
        if False:  # pragma: no cover - unreachable by construction
            self.unreachable()

    def unreachable(self) -> RemovalCoordinator:
        """Retain every coordinator call no execution reaches."""
        return unreachable_helper()


class ConstantExpressionPurgeBoundary:
    """A boundary whose coordinator calls sit behind a folded-false branch."""

    def handle(self) -> None:
        """Call the coordinator only under a provably false comparison."""
        if 1 == 0:  # pragma: no cover - unreachable by construction
            self.unreachable()

    def unreachable(self) -> RemovalCoordinator:
        """Retain every coordinator call no execution reaches."""
        return unreachable_helper()


class OperandValuedPurgeBoundary:
    """A boundary whose calls sit behind a folded-false boolean expression."""

    def handle(self) -> None:
        """Call the coordinator only under an operand-valued false comparison."""
        if (0 or 2) == True:  # noqa: E712 - provably false at runtime  # pragma: no cover
            self.unreachable()

    def unreachable(self) -> RemovalCoordinator:
        """Retain every coordinator call no execution reaches."""
        return unreachable_helper()


class ShortCircuitPurgeBoundary:
    """A boundary whose calls sit behind a short-circuited false conjunction."""

    def handle(self) -> None:
        """Call the coordinator only under a short-circuited false condition."""
        if False and unreachable_helper():  # pragma: no cover - unreachable
            self.unreachable()

    def unreachable(self) -> RemovalCoordinator:
        """Retain every coordinator call no execution reaches."""
        return unreachable_helper()


def unreachable_helper() -> RemovalCoordinator:
    """Retain every coordinator call no executing path reaches."""
    coordinator = RemovalCoordinator(RemovalBoundary.PURGE)
    coordinator.discharge_stage(RemovalAction.REFUSE)
    coordinator.discharge_stage(RemovalAction.DELETE)
    coordinator.discharge_stage(RemovalAction.RECORD)
    coordinator.discharge_stage(RemovalAction.INVALIDATE)
    coordinator.finish()
    return coordinator
