"""Project identity resolution helpers.

The canonical identity model is:
- slug: filesystem/service identifier
- package: Python import package
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from quickscale_cli.schema.config_schema import QuickScaleConfig, validate_config

if TYPE_CHECKING:
    from quickscale_cli.schema.state_schema import QuickScaleState


class ProjectIdentityResolutionError(ValueError):
    """Raised when project identity resolution must fail explicitly."""


@dataclass(frozen=True)
class ProjectIdentity:
    """Resolved project identity."""

    slug: str
    package: str


def derive_package_from_slug(slug: str) -> str:
    """Default package derivation from slug."""
    return slug.replace("-", "_")


def identity_from_config(config: QuickScaleConfig) -> ProjectIdentity:
    """Create identity from validated config object."""
    return ProjectIdentity(slug=config.project.slug, package=config.project.package)


def identity_from_state(state: QuickScaleState) -> ProjectIdentity:
    """Create identity from loaded state object."""
    return ProjectIdentity(
        slug=state.project.slug,
        package=state.project.package,
    )


def load_identity_from_config_file(
    project_path: Path,
    *,
    strict: bool = False,
) -> ProjectIdentity | None:
    """Load identity from quickscale.yml if present.

    When strict is true, malformed config must fail explicitly instead of
    falling back to other identity sources.
    """
    config_path = project_path / "quickscale.yml"
    if not config_path.exists():
        return None

    try:
        config = validate_config(config_path.read_text())
        return identity_from_config(config)
    except Exception as error:
        if strict:
            raise ProjectIdentityResolutionError(
                f"Failed to resolve project identity from quickscale.yml: {error}"
            ) from error
        return None


def load_identity_from_state_file(
    project_path: Path,
    *,
    strict: bool = False,
) -> ProjectIdentity | None:
    """Load identity from .quickscale/state.yml if present.

    When strict is true, malformed state must fail explicitly instead of
    falling back to an unresolved identity.
    """
    from quickscale_cli.schema.state_schema import StateManager

    try:
        state = StateManager(project_path).load()
    except Exception as error:
        if strict:
            raise ProjectIdentityResolutionError(
                "Failed to resolve project identity from .quickscale/state.yml: "
                f"{error}"
            ) from error
        return None

    if state is None:
        return None
    return identity_from_state(state)


def resolve_project_identity(
    project_path: Path,
    *,
    config: QuickScaleConfig | None = None,
    state: QuickScaleState | None = None,
    strict: bool = False,
) -> ProjectIdentity:
    """Resolve project identity using explicit context first, then files.

    Resolution order:
    1) explicit config argument
    2) explicit state argument
    3) quickscale.yml in project root
    4) .quickscale/state.yml

    Raises:
        ValueError: if identity cannot be resolved
    """
    if config is not None:
        return identity_from_config(config)
    if state is not None:
        return identity_from_state(state)

    from_config = load_identity_from_config_file(project_path, strict=strict)
    if from_config is not None:
        return from_config

    from_state = load_identity_from_state_file(project_path, strict=strict)
    if from_state is not None:
        return from_state

    message = (
        "Unable to resolve project identity. Expected quickscale.yml or "
        ".quickscale/state.yml with project.slug and project.package."
    )

    if strict:
        raise ProjectIdentityResolutionError(message)

    raise ValueError(message)
