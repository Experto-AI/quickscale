"""Route resolution and context assembly for the DR command surface.

Implementation detail of :mod:`quickscale_cli.commands.dr_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from dataclasses import dataclass

import click

from quickscale_core.utils.project_identity import ProjectIdentity
from quickscale_core.utils.theme_validation import ThemeValidationError

import quickscale_cli.commands.development_commands as _development_commands
import quickscale_core.utils.project_identity as _project_identity
import quickscale_cli.utils._railway_project as _railway_project
import quickscale_core.utils.theme_validation as _theme_validation
import pathlib as _pathlib


@dataclass(frozen=True)
class DrRouteSpec:
    """Immutable route contract for one DR workflow."""

    label: str
    source_kind: str
    source_environment: str
    target_kind: str
    target_environment: str

    def source_requires_service(self) -> bool:
        return self.source_kind == "railway"

    def target_requires_service(self) -> bool:
        return self.target_kind == "railway"

    def involves_production(self) -> bool:
        return "railway-production" in {
            self.source_environment,
            self.target_environment,
        }


@dataclass(frozen=True)
class DisasterRecoveryContext:
    """Resolved route context for one DR command execution."""

    route: DrRouteSpec
    identity: ProjectIdentity
    source_service: str | None
    target_service: str | None
    source_railway_environment: str | None
    target_railway_environment: str | None
    source_runtime_variables: dict[str, str]
    target_runtime_variables: dict[str, str]


_DR_ROUTES: dict[str, DrRouteSpec] = {
    "local-to-railway-develop": DrRouteSpec(
        label="local-to-railway-develop",
        source_kind="local",
        source_environment="local",
        target_kind="railway",
        target_environment="railway-develop",
    ),
    "railway-develop-to-railway-production": DrRouteSpec(
        label="railway-develop-to-railway-production",
        source_kind="railway",
        source_environment="railway-develop",
        target_kind="railway",
        target_environment="railway-production",
    ),
    "railway-production-to-railway-develop": DrRouteSpec(
        label="railway-production-to-railway-develop",
        source_kind="railway",
        source_environment="railway-production",
        target_kind="railway",
        target_environment="railway-develop",
    ),
}
_ROUTE_CHOICE = click.Choice(tuple(_DR_ROUTES), case_sensitive=True)


def _resolve_route(route: str) -> DrRouteSpec:
    return _DR_ROUTES[route]


def _resolve_project_identity() -> ProjectIdentity:
    try:
        return _project_identity.resolve_project_identity(_pathlib.Path.cwd())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _validate_route_services(
    route: DrRouteSpec,
    *,
    source_service: str | None,
    target_service: str | None,
    include_target: bool,
) -> None:
    if route.source_requires_service() and not source_service:
        raise click.ClickException(
            f"Route '{route.label}' requires --source-service for the Railway source."
        )
    if include_target and route.target_requires_service() and not target_service:
        raise click.ClickException(
            f"Route '{route.label}' requires --target-service for the Railway target."
        )


def _fetch_railway_runtime_variables(
    *,
    service: str,
    railway_environment: str | None,
    role: str,
) -> dict[str, str]:
    try:
        variables = _railway_project.get_railway_variables(
            service=service,
            environment=railway_environment,
        )
    except ValueError as exc:
        label = service
        if railway_environment:
            label = f"{service} ({railway_environment})"
        raise click.ClickException(
            f"Railway CLI output format error for {role} service '{label}': {exc}"
        ) from exc
    if variables is None:
        label = service
        if railway_environment:
            label = f"{service} ({railway_environment})"
        raise click.ClickException(
            f"Unable to load Railway variables for the {role} service '{label}'."
        )
    return variables


def _build_context(
    route_label: str,
    *,
    source_service: str | None,
    target_service: str | None,
    source_railway_environment: str | None,
    target_railway_environment: str | None,
    include_target: bool,
) -> DisasterRecoveryContext:
    # Run read-only theme preflight before any validation or probe.
    try:
        _theme_validation.validate_theme_preflight(_pathlib.Path.cwd())
    except ThemeValidationError as exc:
        raise click.ClickException(
            "Theme validation failed for DR command:\n"
            + "\n".join(f"  • {line}" for line in str(exc).splitlines())
            + "\n\n"
            "Update project.theme to 'showcase_react' in all present "
            "configuration files before running DR commands."
        ) from exc

    _development_commands._validate_project_and_docker()
    route = _resolve_route(route_label)
    _validate_route_services(
        route,
        source_service=source_service,
        target_service=target_service,
        include_target=include_target,
    )
    identity = _resolve_project_identity()

    source_runtime_variables: dict[str, str] = {}
    if route.source_requires_service():
        assert source_service is not None  # noqa: S101 - internal invariant guaranteed by the caller
        source_runtime_variables = _fetch_railway_runtime_variables(
            service=source_service,
            railway_environment=source_railway_environment,
            role="source",
        )

    target_runtime_variables: dict[str, str] = {}
    if include_target and route.target_requires_service():
        assert target_service is not None  # noqa: S101 - internal invariant guaranteed by the caller
        target_runtime_variables = _fetch_railway_runtime_variables(
            service=target_service,
            railway_environment=target_railway_environment,
            role="target",
        )

    return DisasterRecoveryContext(
        route=route,
        identity=identity,
        source_service=source_service,
        target_service=target_service,
        source_railway_environment=source_railway_environment,
        target_railway_environment=target_railway_environment,
        source_runtime_variables=source_runtime_variables,
        target_runtime_variables=target_runtime_variables,
    )
