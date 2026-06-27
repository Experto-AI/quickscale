"""Core-safe types for the apply step extraction boundary.

This module defines the protocol/type seam that extracted apply step bodies
must use.  The seam is the *only* allowed extraction boundary — no step body
may import ``quickscale_cli``, and no step body may reach outside the types
defined here.

**Allowed imports for this module:**
- Standard library types (``dataclasses``, ``Path``, ``Protocol``, etc.)
- Canonical core schema types from ``quickscale_core.schema.*`` (under
  ``TYPE_CHECKING`` to avoid runtime coupling with non-schema callers).
- Injected callback protocol definitions.

**Design invariants:**
1. Every extracted step body receives a :class:`StepContext` and returns a
   :class:`StepOutcome`.
2. The context carries only core schema data, plain paths/flags, and injected
   callable protocols — no ``quickscale_cli`` references.
3. ``StepReporter`` and ``StepHook`` protocols let CLI-level reporting and
   failure handling be injected at the call site without importing CLI code
   into the core.
4. Phase 1 establishes the abstraction.  No step bodies are extracted yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Step outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepOutcome:
    """Immutable result of a single apply step execution.

    Attributes:
        success: Whether the step completed without failure.
        message: Human-readable outcome message for logging or display.
        failed_step_label: The ``failed_step`` label to use when this step
            aborts the apply pipeline, or ``None`` for best-effort /
            informational steps that do not abort.
    """

    success: bool
    message: str = ""
    failed_step_label: str | None = None


# ---------------------------------------------------------------------------
# Step context — the data contract for extracted step bodies
# ---------------------------------------------------------------------------


@dataclass
class StepContext:
    """Context passed to each extracted apply step body.

    This is the canonical data contract for step extraction.  It carries
    only core schema objects, plain paths/flags, and injected callables.
    No ``quickscale_cli`` types appear here.

    Attributes:
        output_path: The generated project root directory.
        qs_config: The validated desired-state configuration
            (:class:`~quickscale_core.schema.config_schema.QuickScaleConfig`).
        existing_state: The current applied state
            (:class:`~quickscale_core.schema.state_schema.QuickScaleState`)
            or ``None`` for fresh projects.
        state_snapshot: The post-embed state snapshot built during apply,
            or ``None`` before embedding.
        manifests: Loaded module manifests keyed by module name
            (``dict[str, ModuleManifest]``).
        delta: The computed delta between desired and applied state
            (:class:`~quickscale_core.schema.delta.ConfigDelta`).
        embedded_modules: List of module names embedded in the current
            apply pass.
        no_docker: Flag indicating whether Docker operations are skipped.
        verbose_docker: Flag for verbose Docker build output.
        reporter: Injected callback for progress/status messages.
        failure_hook: Injected callback invoked on step failure.
    """

    output_path: Path
    qs_config: Any = None  # QuickScaleConfig from quickscale_core.schema.config_schema
    existing_state: Any | None = None
    state_snapshot: Any | None = None
    checkpoint_tree_id: str | None = None
    manifests: dict[str, Any] = field(default_factory=dict)
    delta: Any | None = None  # ConfigDelta from quickscale_core.schema.delta
    embedded_modules: list[str] = field(default_factory=list)
    provenance_payloads: dict[str, Any] = field(default_factory=dict)
    embed_failed_module: str | None = None
    embed_commit_failure: bool = False
    no_docker: bool = False
    verbose_docker: bool = False
    reporter: StepReporter | None = None
    failure_hook: StepHook | None = None


# ---------------------------------------------------------------------------
# Injected callback protocols
# ---------------------------------------------------------------------------


class StepReporter(Protocol):
    """Protocol for reporting step progress/status.

    The callable signature matches ``click.echo``-style reporting so that
    CLI-level adapters can be injected directly without wrapping.
    """

    def __call__(self, message: str, *, ok: bool = True) -> None: ...


class StepHook(Protocol):
    """Protocol for failure hooks invoked on step error.

    Implementations handle abort-side effects such as persisting recovery
    state or printing failure summaries.  The hook is called *after* the
    step body has returned an unsuccessful :class:`StepOutcome`.
    """

    def __call__(
        self,
        step_id: str,
        message: str,
        *,
        ctx: StepContext,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Step body protocol
# ---------------------------------------------------------------------------


class ApplyStepProtocol(Protocol):
    """Protocol that every extracted apply step body must satisfy.

    A step body is a callable that receives a :class:`StepContext` and
    returns a :class:`StepOutcome`.  Step bodies are the unit of
    extraction — each maps to one entry in the
    :data:`~quickscale_core.apply.step.APPLY_STEPS` registry.

    Phase 2 will extract concrete step bodies; Phase 1 only defines the
    protocol.
    """

    def __call__(self, ctx: StepContext) -> StepOutcome: ...


__all__ = [
    "ApplyStepProtocol",
    "StepContext",
    "StepHook",
    "StepOutcome",
    "StepReporter",
]
