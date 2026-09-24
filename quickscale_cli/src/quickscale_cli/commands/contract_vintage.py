"""Shared project-contract vintage checks for CLI command boundaries.

SA207 declares generated-project contract changes once in the packaged
``quickscale_core`` declaration (``data/project_contract.yml``) instead of
copying adoption prose into every module manifest.  The project-level steps
and the remaining module-specific vintages are enforced together here.

A step that declares an ``id`` is satisfied only while the project records
that id in ``adopted_contract_steps``; a step without an id keeps the version
comparison, which is sound for boundaries that landed at a release.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

import click

from quickscale_core.advisory_lock import (
    AdvisoryLock,
    AdvisoryLockContentionError,
)
from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest import (
    ContractVintage,
    ModuleManifest,
    ProjectContractStep,
    load_project_contract_vintage,
    parse_version_tuple,
)
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.state_schema import QuickScaleState


ACKNOWLEDGE_CONTRACT_VINTAGE_OPTION = "--acknowledge-contract-vintage"
CONFIRM_CONTRACT_ADOPTION_OPTION = "--confirm-contract-adoption"


def load_declared_project_steps() -> tuple[ProjectContractStep, ...]:
    """Load the shipped generated-project contract declaration, failing hard."""
    try:
        return tuple(load_project_contract_vintage().steps)
    except Exception as error:
        raise click.ClickException(
            f"Unable to read the generated-project contract declaration: {error}"
        ) from error


def declared_project_vintage(steps: Sequence[ProjectContractStep]) -> str:
    """Return the highest declared step minimum — the recordable vintage."""
    if not steps:
        raise click.ClickException(
            "The generated-project contract declaration declares no steps; "
            "there is nothing to record."
        )
    return max(steps, key=lambda step: parse_version_tuple(step.minimum)).minimum


def declared_adoption_step_ids(module_names: Iterable[str] = ()) -> list[str]:
    """Every adoption step id the shipped declarations currently require.

    The project-level declaration contributes its steps; each shipped module
    manifest contributes its own id when it declares one.
    """
    step_ids = [step.id for step in load_declared_project_steps()]
    for manifest in load_shipped_contract_manifests(module_names).values():
        vintage = manifest.contract_vintage
        if vintage is not None and vintage.id:
            step_ids.append(vintage.id)
    return step_ids


def check_contract_vintage(
    project_contract: str | None,
    manifests: Mapping[str, ModuleManifest] | None,
    *,
    requirements: Mapping[str, ContractVintage] | None = None,
    project_steps: Sequence[ProjectContractStep] = (),
    adopted_steps: Sequence[str] | None = None,
) -> dict[str, object]:
    """Compare declared requirements with a project's recorded contract."""
    adopted = set(adopted_steps or ())

    declared: dict[str, ContractVintage] = {}
    for module_name, manifest in (manifests or {}).items():
        if manifest.contract_vintage is not None:
            declared[module_name] = manifest.contract_vintage
    declared.update(requirements or {})

    project_tuple = parse_version_tuple(project_contract) if project_contract else (0,)

    project_steps_behind: list[dict[str, object]] = []
    for step in project_steps:
        if step.id not in adopted:
            project_steps_behind.append(
                {
                    "id": step.id,
                    "minimum": step.minimum,
                    "title": step.title,
                    "manual_adoption_steps": list(step.manual_adoption_steps),
                }
            )

    consumers_behind: list[dict[str, object]] = []
    for consumer, vintage in declared.items():
        if vintage.id is not None:
            behind = vintage.id not in adopted
        else:
            behind = project_tuple < parse_version_tuple(vintage.minimum)
        if behind:
            consumers_behind.append(
                {
                    "module": consumer,
                    "minimum": vintage.minimum,
                    "manual_adoption_steps": list(vintage.manual_adoption_steps),
                }
            )

    return {
        "project_contract": project_contract,
        "project_steps_behind": project_steps_behind,
        "project_step_count": len(project_steps),
        "project_steps_behind_count": len(project_steps_behind),
        "modules_behind": consumers_behind,
        "module_count": len(declared),
        "modules_behind_count": len(consumers_behind),
    }


def load_shipped_contract_manifests(
    module_names: Iterable[str],
) -> dict[str, ModuleManifest]:
    """Load current shipped manifests rather than a project's older copies."""
    manifests: dict[str, ModuleManifest] = {}
    for module_name in sorted(set(module_names)):
        try:
            manifests[module_name] = load_module_manifest_with_fallback(module_name)
        except Exception as error:
            raise click.ClickException(
                f"Unable to check the contract vintage for module {module_name!r}: "
                f"{error}"
            ) from error
    return manifests


def enforce_contract_vintage(
    state: QuickScaleState | None,
    manifests: Mapping[str, ModuleManifest] | None,
    *,
    operation: str,
    acknowledged: bool,
    requirements: Mapping[str, ContractVintage] | None = None,
    project_steps: Sequence[ProjectContractStep] | None = None,
) -> None:
    """Refuse an operation when upgradable code outruns generated files."""
    if state is None:
        return

    declared_steps = (
        tuple(project_steps)
        if project_steps is not None
        else load_declared_project_steps()
    )
    diagnostics = check_contract_vintage(
        state.project.project_contract,
        manifests,
        requirements=requirements,
        project_steps=declared_steps,
        adopted_steps=state.project.adopted_contract_steps,
    )
    steps_behind = cast(list[dict[str, object]], diagnostics["project_steps_behind"])
    consumers_behind = cast(list[dict[str, object]], diagnostics["modules_behind"])
    if not steps_behind and not consumers_behind:
        return

    if acknowledged:
        click.secho(
            f"⚠️  Contract-vintage gap explicitly acknowledged for {operation}.",
            fg="yellow",
            err=True,
        )
        return

    project_contract = state.project.project_contract or "unknown (legacy project)"
    click.secho(
        f"\n❌ Cannot run {operation}: project contract {project_contract} is behind.",
        fg="red",
        err=True,
        bold=True,
    )
    for entry in steps_behind:
        click.echo(
            f"  • generated project ({entry['id']}) requires project_contract"
            f" >= {entry['minimum']}",
            err=True,
        )
        click.echo(f"    - {entry['title']}", err=True)
        for step in cast(list[str], entry["manual_adoption_steps"]):
            click.echo(f"    - {step}", err=True)
    for entry in consumers_behind:
        click.echo(
            f"  • {entry['module']} requires project_contract >= {entry['minimum']}",
            err=True,
        )
        adoption_steps = cast(list[str], entry["manual_adoption_steps"])
        for step in adoption_steps:
            click.echo(f"    - {step}", err=True)
    click.echo(
        "\nComplete every adoption step before retrying. If those files are already "
        f"updated, re-run with {CONFIRM_CONTRACT_ADOPTION_OPTION} to record the "
        f"adoption in .quickscale/state.yml, or with "
        f"{ACKNOWLEDGE_CONTRACT_VINTAGE_OPTION} to acknowledge the compatibility "
        "boundary for this invocation only.",
        err=True,
    )
    raise click.Abort()


def enforce_shipped_contract_vintage(
    state: QuickScaleState | None,
    module_names: Iterable[str],
    *,
    operation: str,
    acknowledged: bool,
    project_steps: Sequence[ProjectContractStep] | None = None,
) -> None:
    """Enforce current shipped requirements for an existing project."""
    if state is None:
        return
    enforce_contract_vintage(
        state,
        load_shipped_contract_manifests(module_names),
        operation=operation,
        acknowledged=acknowledged,
        project_steps=project_steps,
    )


def record_contract_adoption(
    state: QuickScaleState | None,
    project_path: Path,
) -> str | None:
    """Record the declared project vintage after the user confirms adoption.

    Advances ``project_contract`` in ``.quickscale/state.yml`` and records
    every declared adoption step id, so a project that has adopted every step
    no longer needs the per-invocation acknowledgement flag and a project
    generated before a step existed cannot pass on a shared version alone.
    """
    if state is None:
        return None

    steps = load_declared_project_steps()
    recorded = declared_project_vintage(steps)
    declared_steps = declared_adoption_step_ids(state.modules)
    # Union with the previously recorded ids: an older CLI confirming a newer
    # project's state must not discard ids it does not declare.
    adopted = list(
        dict.fromkeys([*(state.project.adopted_contract_steps or ()), *declared_steps])
    )
    current = state.project.project_contract
    already_recorded = (
        current is not None
        and parse_version_tuple(current) >= parse_version_tuple(recorded)
        and set(declared_steps) <= set(state.project.adopted_contract_steps or ())
    )
    if already_recorded:
        click.secho(
            f"✅ Project contract already recorded as {current}.",
            fg="green",
        )
        return current

    # Never move a recorded vintage backwards: a newer state read by an older
    # CLI keeps its greater contract while still recording the step ids.
    target_contract = recorded
    if current is not None and parse_version_tuple(current) > parse_version_tuple(
        recorded
    ):
        target_contract = current

    state.project.project_contract = target_contract
    state.project.adopted_contract_steps = adopted
    try:
        ProjectStateManager(project_path).save_state(state)
    except Exception as error:
        raise click.ClickException(
            f"Unable to record the project contract adoption: {error}"
        ) from error
    click.secho(
        f"✅ Recorded generated-project contract adoption: {target_contract}",
        fg="green",
    )
    click.echo(f"   Adopted steps: {', '.join(adopted)}")
    return target_contract


def record_confirmed_adoption(project_path: Path, *, operation: str) -> str | None:
    """Reload current state under the advisory lock, then record adoption.

    Recording from a state object loaded before the command's own preflight
    could overwrite a concurrent locked change, so the write re-reads the
    authoritative state while holding the project lock.
    """
    lock = AdvisoryLock(project_path, operation=operation)
    try:
        lock.acquire()
    except AdvisoryLockContentionError as error:
        raise click.ClickException(
            f"Unable to acquire the project state lock to record the contract "
            f"adoption: {error}"
        ) from error
    try:
        state = ProjectStateManager(project_path).load_state()
        return record_contract_adoption(state, project_path)
    finally:
        lock.release()
