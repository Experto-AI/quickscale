#!/usr/bin/env python3
"""
Refresh every SHA-pinned third-party action to its latest release (SA212).

Operator tool for the release procedure, not a CI gate: it needs network
access, so no CI context runs it and it has no gate-registry row.

Catalog-owned pins — the action refs the generated hosted jobs carry — are
moved by rewriting the constants in ``scripts/sync_ci_gate_jobs.py`` and letting
``--write`` regenerate the marked region; the tool never edits that region
itself.  Every other pin in ``.github/workflows/`` is rewritten in place,
keeping the trailing version comment in step with the resolved tag.

The ``--workflows``, ``--generator``, and ``--registry`` overrides exist for
fixture testing; the release procedure runs the defaults, which stay in
lockstep with each other.

Usage:
    poetry run python scripts/refresh_action_pins.py [--check]

Exit codes:
    0 - clean (``--check``) or successfully refreshed
    1 - stale pins found (``--check`` only)
    2 - malformed input, a failed lookup, or a failed generator run
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:  # pragma: no cover - Poetry supplies PyYAML
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS = ROOT / ".github" / "workflows"
DEFAULT_GENERATOR = ROOT / "scripts" / "sync_ci_gate_jobs.py"
DEFAULT_REGISTRY = ROOT / "scripts" / "gate_registry.json"
GENERATED_WORKFLOW_NAME = "ci.yml"
# The generated hosted jobs' action refs, as ``(ref constant, comment constant)``
# in scripts/sync_ci_gate_jobs.py.  The tool edits only these values.
CATALOG_CONSTANTS: tuple[tuple[str, str], ...] = (
    ("CHECKOUT_REF", "CHECKOUT_COMMENT"),
    ("SETUP_PYTHON_REF", "SETUP_PYTHON_COMMENT"),
    ("INSTALL_POETRY_REF", "INSTALL_POETRY_COMMENT"),
)
COMMAND_TIMEOUT = 180.0
EXIT_CLEAN = 0
EXIT_STALE = 1
EXIT_INFRASTRUCTURE = 2
PINNED_REF_RE = re.compile(r"[0-9a-fA-F]{40}")
_PIN_RE = re.compile(
    r"^(?P<indent>\s*)(?P<dash>-\s+)?(?P<key>uses:)(?P<gap>\s+)"
    r"(?P<quote>[\"']?)"
    r"(?P<action>[\w.-]+/[\w.-]+(?:/[\w./-]+)?)@(?P<sha>[0-9a-fA-F]{40})"
    r"(?P=quote)(?:(?P<sep>\s*)#\s*(?P<comment>\S(?:.*\S)?))?\s*$"
)
_PINNED_VALUE_FULL_RE = re.compile(
    r"^(?P<action>[\w.-]+/[\w.-]+(?:/[\w./-]+)?)@(?P<sha>[0-9a-fA-F]{40})$"
)
_TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")


class RefreshError(RuntimeError):
    """An expected refresh failure, reported as infrastructure exit 2."""


@dataclass(frozen=True)
class Release:
    """The latest release of one action repository."""

    tag: str
    sha: str


@dataclass(frozen=True)
class Pin:
    """One ``uses: owner/repo@<sha>`` reference in a workflow file."""

    path: Path
    line_number: int
    action: str
    repository: str
    sha: str
    comment: str | None


def _repository(action: str) -> str:
    """Return the ``owner/repo`` a ``uses:`` value resolves to."""
    parts = action.split("/")
    if len(parts) < 2 or not all(parts[:2]):
        raise RefreshError(f"not an action reference: {action!r}")
    return "/".join(parts[:2])


def _iter_uses_nodes(node: Any) -> list[Any]:
    """Return every ``uses`` value node in a composed workflow document."""
    found: list[Any] = []
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == "uses":
                found.append(value_node)
            else:
                found.extend(_iter_uses_nodes(key_node))
            found.extend(_iter_uses_nodes(value_node))
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            found.extend(_iter_uses_nodes(item))
    return found


def _assert_all_pinned_uses_discovered(path: Path, text: str, pins: list[Pin]) -> None:
    """
    Fail closed unless every pinned ``uses`` value is a discovered single line.

    Line scanning cannot see values YAML splits across lines, anchors, or flow
    collections, and it can match text that is not a ``uses`` entry at all.  The
    composed document therefore has to account for each discovered pin by source
    position: a pinned value that is not a single-line scalar on its pin's line,
    or a discovered pin no parsed value claims, is an unsupported form.
    """
    if yaml is None:  # pragma: no cover - Poetry supplies PyYAML
        raise RefreshError("PyYAML is required to verify workflow pin discovery")
    try:
        document = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise RefreshError(f"cannot parse {path}: {exc}") from exc
    if document is None:
        raise RefreshError(f"{path}: workflow is empty")
    lines = text.splitlines()
    parsed: set[tuple[int, str, str]] = set()
    for node in _iter_uses_nodes(document):
        if not isinstance(node, yaml.ScalarNode) or not isinstance(node.value, str):
            raise RefreshError(f"{path}: unsupported uses value")
        match = _PINNED_VALUE_FULL_RE.fullmatch(node.value.strip())
        if match is None:
            continue
        if node.start_mark.line != node.end_mark.line:
            raise RefreshError(
                f"{path}: pinned action reference is not in a supported single-line form: "
                f"{node.value}"
            )
        number = node.start_mark.line + 1
        raw = lines[number - 1] if 0 < number <= len(lines) else ""
        line_match = _PIN_RE.match(raw)
        if (
            line_match is None
            or line_match["action"] != match["action"]
            or line_match["sha"] != match["sha"]
        ):
            raise RefreshError(
                f"{path}: pinned action reference is not in a supported single-line form: "
                f"{node.value}"
            )
        parsed.add((number, match["action"], match["sha"]))
    discovered = {(pin.line_number, pin.action, pin.sha) for pin in pins}
    if parsed != discovered:
        difference = sorted(parsed ^ discovered)
        raise RefreshError(
            f"{path}: workflow pin discovery does not match the parsed uses values: {difference}"
        )


def discover_pins(workflows_dir: Path) -> list[Pin]:
    """Return every SHA-pinned third-party action reference under a directory."""
    if not workflows_dir.is_dir():
        raise RefreshError(f"workflow directory not found: {workflows_dir}")
    paths = sorted({*workflows_dir.rglob("*.yml"), *workflows_dir.rglob("*.yaml")})
    pins: list[Pin] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RefreshError(f"cannot read {path}: {exc}") from exc
        file_pins: list[Pin] = []
        for index, line in enumerate(text.splitlines(), start=1):
            match = _PIN_RE.match(line)
            if match is None:
                continue
            action = match["action"]
            file_pins.append(
                Pin(
                    path=path,
                    line_number=index,
                    action=action,
                    repository=_repository(action),
                    sha=match["sha"],
                    comment=match["comment"],
                )
            )
        _assert_all_pinned_uses_discovered(path, text, file_pins)
        pins.extend(file_pins)
    return pins


def _pin_is_current(pin: Pin, release: Release) -> bool:
    """Return True when a pin already carries the release's SHA and version."""
    return pin.sha.lower() == release.sha and pin.comment == release.tag


def _fetch_json(url: str) -> Any:
    """Fetch one GitHub API document over HTTPS."""
    request = Request(
        url,
        headers={
            "User-Agent": "quickscale-action-pin-refresh/1",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(request, timeout=COMMAND_TIMEOUT) as response:
            document = json.loads(response.read().decode("utf-8"))
    except HTTPError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RefreshError(f"GitHub lookup failed for {url}: {exc}") from exc
    return document


def _require_tag(repository: str, tag: Any) -> str:
    if not isinstance(tag, str) or _TAG_RE.fullmatch(tag) is None:
        raise RefreshError(f"GitHub returned no usable release tag for {repository}")
    return tag


def latest_release(repository: str, fetch: Callable[[str], Any] = _fetch_json) -> Release:
    """Resolve one repository's latest release tag and its commit SHA."""
    api = f"https://api.github.com/repos/{repository}"
    tag: str | None = None
    try:
        release = fetch(f"{api}/releases/latest")
    except HTTPError as exc:
        if exc.code != 404:
            raise RefreshError(f"GitHub lookup failed for {repository}: HTTP {exc.code}") from exc
    else:
        tag_name = release.get("tag_name") if isinstance(release, dict) else None
        tag = _require_tag(repository, tag_name)
    if tag is None:
        try:
            tags = fetch(f"{api}/tags")
        except HTTPError as exc:
            raise RefreshError(f"GitHub lookup failed for {repository}: HTTP {exc.code}") from exc
        first = tags[0] if isinstance(tags, list) and tags else None
        tag = _require_tag(repository, first.get("name") if isinstance(first, dict) else None)
    try:
        commit = fetch(f"{api}/commits/{tag}")
    except HTTPError as exc:
        raise RefreshError(f"GitHub lookup failed for {repository}: HTTP {exc.code}") from exc
    sha = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(sha, str) or PINNED_REF_RE.fullmatch(sha) is None:
        raise RefreshError(f"GitHub returned no usable commit SHA for {repository}@{tag}")
    return Release(tag=tag, sha=sha.lower())


def plan_releases(pins: list[Pin], fetch: Callable[[str], Any] = _fetch_json) -> dict[str, Release]:
    """Resolve every distinct action repository once."""
    plan: dict[str, Release] = {}
    for repository in sorted({pin.repository for pin in pins}):
        plan[repository] = latest_release(repository, fetch)
    return plan


def _load_generator(path: Path) -> ModuleType:
    """Load the workflow generator module for its marker and catalog constants."""
    if not path.is_file():
        raise RefreshError(f"generator not found: {path}")
    spec = importlib.util.spec_from_file_location("refresh_action_pins_generator", path)
    if spec is None or spec.loader is None:
        raise RefreshError(f"could not load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    # ``@dataclass`` resolves annotations through ``sys.modules[cls.__module__]``,
    # so the module must be registered before it executes.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError, SyntaxError) as exc:
        sys.modules.pop(spec.name, None)
        raise RefreshError(f"could not load generator {path}: {exc}") from exc
    return module


def _generated_region(module: ModuleType, workflow: Path) -> tuple[int, int]:
    """Return the 1-based (begin, end) marker lines of the generated job region."""
    try:
        lines = workflow.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RefreshError(f"cannot read {workflow}: {exc}") from exc
    begins = [index for index, line in enumerate(lines, 1) if line == module.JOB_BEGIN]
    ends = [index for index, line in enumerate(lines, 1) if line == module.JOB_END]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise RefreshError(f"{workflow}: generated job markers are missing or ambiguous")
    return begins[0], ends[0]


def _atomic_write_text(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _replace_constant(lines: list[str], path: Path, name: str, value: str) -> None:
    """Replace exactly one ``NAME = "..."`` assignment, preserving its spelling."""
    pattern = re.compile(
        rf"^(?P<name>{re.escape(name)})(?P<sep>\s*=\s*)(?P<quote>[\"'])(?P<old>[^\"']*)"
        r"(?P=quote)(?P<tail>\s*)$"
    )
    hits = [
        (index, match)
        for index, line in enumerate(lines)
        if (match := pattern.match(line.rstrip("\r\n"))) is not None
    ]
    if len(hits) != 1:
        raise RefreshError(f"{path}: expected exactly one {name} assignment, found {len(hits)}")
    index, match = hits[0]
    line = lines[index]
    ending = "\r\n" if line.endswith("\r\n") else "\n"
    lines[index] = (
        f"{name}{match['sep']}{match['quote']}{value}{match['quote']}{match['tail']}{ending}"
    )


def _update_catalog_constants(
    generator_path: Path, module: ModuleType, plan: dict[str, Release]
) -> tuple[list[str], str | None]:
    """Point the catalog's action refs at the planned releases."""
    try:
        original = generator_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RefreshError(f"cannot read {generator_path}: {exc}") from exc
    lines = original.splitlines(keepends=True)
    changes: list[str] = []
    for ref_name, comment_name in CATALOG_CONSTANTS:
        current = getattr(module, ref_name, None)
        if not isinstance(current, str) or "@" not in current:
            raise RefreshError(f"{generator_path}: {ref_name} is not a pinned action ref")
        repository, _, _ = current.rpartition("@")
        release = plan.get(repository)
        if release is None:
            continue
        new_ref = f"{repository}@{release.sha}"
        new_comment = f"# {release.tag}"
        if current == new_ref and getattr(module, comment_name, None) == new_comment:
            continue
        _replace_constant(lines, generator_path, ref_name, new_ref)
        _replace_constant(lines, generator_path, comment_name, new_comment)
        changes.append(f"{generator_path}: {ref_name} -> {new_ref} {new_comment}")
    if not changes:
        return [], None
    _atomic_write_text(generator_path, "".join(lines))
    return changes, original


def _run_generator(generator_path: Path, workflow: Path, registry: Path, *, write: bool) -> None:
    """Run the existing sync entry point against the generated workflow."""
    command = [
        sys.executable,
        str(generator_path),
        "--write" if write else "--check",
        "--workflow",
        str(workflow),
        "--registry",
        str(registry),
    ]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (
            str(generator_path.parent),
            str(Path(__file__).resolve().parent),
            environment.get("PYTHONPATH", ""),
        )
        if part
    )
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RefreshError(f"could not run {generator_path}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RefreshError(
            f"{generator_path.name} {'--write' if write else '--check'} "
            f"exited {completed.returncode}: {detail}"
        )


def _rewrite_direct_pins(
    pins: list[Pin],
    plan: dict[str, Release],
    *,
    generated_workflow: Path,
    region: tuple[int, int],
) -> list[str]:
    """Rewrite stale pins the generator does not own, grouped per file."""
    grouped: dict[Path, list[Pin]] = {}
    for pin in pins:
        if _pin_is_current(pin, plan[pin.repository]):
            continue
        if pin.path == generated_workflow and region[0] < pin.line_number < region[1]:
            continue
        grouped.setdefault(pin.path, []).append(pin)
    changes: list[str] = []
    for path, file_pins in grouped.items():
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError as exc:
            raise RefreshError(f"cannot read {path}: {exc}") from exc
        for pin in file_pins:
            index = pin.line_number - 1
            line = lines[index]
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            match = _PIN_RE.match(line.rstrip("\r\n"))
            if match is None or match["sha"] != pin.sha or match["action"] != pin.action:
                raise RefreshError(f"{path}:{pin.line_number}: pin changed during refresh")
            release = plan[pin.repository]
            lines[index] = (
                f"{match['indent']}{match['dash'] or ''}{match['key']}{match['gap']}"
                f"{match['quote']}{pin.action}@{release.sha}{match['quote']} "
                f"# {release.tag}{ending}"
            )
            changes.append(f"{path}:{pin.line_number}: {pin.action} -> {release.tag}")
        _atomic_write_text(path, "".join(lines))
    return changes


def refresh(
    workflows_dir: Path,
    generator_path: Path,
    registry_path: Path,
    *,
    check: bool,
    fetch: Callable[[str], Any] = _fetch_json,
) -> int:
    """Report stale pins, or refresh them and certify the generated workflow."""
    module = _load_generator(generator_path)
    pins = discover_pins(workflows_dir)
    if not pins:
        raise RefreshError(f"no SHA-pinned actions found under {workflows_dir}")
    plan = plan_releases(pins, fetch)
    if check:
        stale = [pin for pin in pins if not _pin_is_current(pin, plan[pin.repository])]
        for pin in stale:
            release = plan[pin.repository]
            comment = f" # {pin.comment}" if pin.comment else ""
            print(
                f"{pin.path}:{pin.line_number}: {pin.action}@{pin.sha}{comment} "
                f"-> {release.tag} ({release.sha})"
            )
        if stale:
            print(f"stale action pins: {len(stale)}")
            return EXIT_STALE
        print(f"action pins are current: {len(pins)}")
        return EXIT_CLEAN
    generated_workflow = workflows_dir / GENERATED_WORKFLOW_NAME
    _generated_region(module, generated_workflow)
    catalog_changes, original_catalog = _update_catalog_constants(generator_path, module, plan)
    try:
        _run_generator(generator_path, generated_workflow, registry_path, write=True)
    except RefreshError:
        # Leave the tree consistent: a failed regeneration must not strand an
        # updated catalog beside a stale generated region.
        if original_catalog is not None:
            _atomic_write_text(generator_path, original_catalog)
        raise
    region = _generated_region(module, generated_workflow)
    direct_changes = _rewrite_direct_pins(
        discover_pins(workflows_dir),
        plan,
        generated_workflow=generated_workflow,
        region=region,
    )
    remaining = [
        pin
        for pin in discover_pins(workflows_dir)
        if not _pin_is_current(pin, plan[pin.repository])
    ]
    if remaining:
        stale = ", ".join(f"{pin.path}:{pin.line_number}" for pin in remaining)
        raise RefreshError(f"pins still stale after refresh: {stale}")
    _run_generator(generator_path, generated_workflow, registry_path, write=False)
    for change in (*catalog_changes, *direct_changes):
        print(change)
    print(f"action pins refreshed: {len(pins)}")
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    """Run the pin refresh and return its process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale pins without writing anything",
    )
    parser.add_argument("--workflows", type=Path, default=DEFAULT_WORKFLOWS)
    parser.add_argument("--generator", type=Path, default=DEFAULT_GENERATOR)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    try:
        return refresh(
            args.workflows,
            args.generator,
            args.registry,
            check=args.check,
            fetch=_fetch_json,
        )
    except RefreshError as exc:
        print(f"action pin refresh infrastructure failure: {exc}", file=sys.stderr)
        return EXIT_INFRASTRUCTURE


if __name__ == "__main__":
    raise SystemExit(main())
