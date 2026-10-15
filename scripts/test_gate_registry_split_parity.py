"""
Behavioral controls for the SA267(a) gate-registry script split.

``check_gate_parity`` and ``sync_ci_gate_jobs`` keep their pre-split behavior
through private ``_``-prefixed siblings.  SA267 has closed, so SA278 retired
the pre-split surface pins; these controls keep the split's structural
invariants and the exact diagnostics and generated texts captured from the
pre-split modules as behavioral tests, so a later change cannot silently
drop, reorder, or reword them.

SA275(a) deleted the gate-order tuples, the hosted/publish/help catalogs, and
the copy-equality refusals they fed; the registry metadata fields that
replaced them are validated through the schema diagnostics exercised here.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import _gate_registry_schema as schema
import check_gate_parity
import pytest
import sync_ci_gate_jobs
from _sync_ci_gate_catalog import (
    DOCS_TABLE_BEGIN,
    DOCS_TABLE_END,
    E2E_PATHS_END,
    JOB_BEGIN,
    JOB_END,
    PUBLISH_END,
)

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_gate_registry_metadata": "_gate_registry_schema",
    "_gate_registry_schema": "check_gate_parity",
    "_sync_ci_gate_catalog": "sync_ci_gate_jobs",
    "_sync_ci_gate_core": "sync_ci_gate_jobs",
    "_sync_ci_gate_docs": "sync_ci_gate_jobs",
    "_sync_ci_gate_e2e": "sync_ci_gate_jobs",
    "_sync_ci_gate_help": "sync_ci_gate_jobs",
    "_sync_ci_gate_make": "sync_ci_gate_jobs",
    "_sync_ci_gate_publish": "sync_ci_gate_jobs",
    "_sync_ci_gate_regions": "sync_ci_gate_jobs",
}

# ---------------------------------------------------------------------------
# Registry schema findings captured from the pre-split module
# ---------------------------------------------------------------------------

_CONTEXTS = {
    name: f"{name} context"
    for name in ("local-serial", "local-parallel", "hosted", "publish", "e2e-trigger")
}


def _gate(**over: Any) -> dict[str, Any]:
    gate = {
        "id": "gate-a",
        "description": "A gate",
        "required_contexts": ["hosted"],
        "bindings": {"make_target": "check-a", "ci_job": "job-a", "local_ci_stage": None},
        "hosted": {"order": 1, "display_name": "Gate A", "check_step_name": "Run gate a"},
        "depends_on": [],
        "trigger_inputs": [],
    }
    gate.update(over)
    return gate


def _registry(**over: Any) -> dict[str, Any]:
    data = {
        "schema_version": 1,
        "description": "Test registry",
        "contexts": dict(_CONTEXTS),
        "gates": [_gate()],
    }
    data.update(over)
    return data


def _mutated(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    data = _registry()
    change(data)
    return data


def _second_gate(**over: Any) -> dict[str, Any]:
    gate = _gate(
        id="gate-b",
        bindings={"make_target": "check-b", "ci_job": "job-b", "local_ci_stage": None},
        hosted={"order": 2, "display_name": "Gate B", "check_step_name": "Run gate b"},
    )
    gate.update(over)
    return gate


#: ``(case, builder, expected path, expected message)``; ``path``/``message``
#: are the exact pre-split diagnostics.  The valid case expects no error.
REGISTRY_FINDING_CASES: tuple[tuple[str, Callable[[], Any], str, str], ...] = (
    ("not_object", lambda: [], "", "must be a JSON object"),
    (
        "top_unknown_key",
        lambda: _mutated(lambda d: d.__setitem__("extra", 1)),
        "",
        "unknown top-level key(s): extra",
    ),
    (
        "top_missing_key",
        lambda: _mutated(lambda d: d.pop("description")),
        "",
        "missing required top-level key(s): description",
    ),
    (
        "schema_bool",
        lambda: _mutated(lambda d: d.__setitem__("schema_version", True)),
        "schema_version",
        "schema_version must be a non-boolean integer (got bool)",
    ),
    (
        "schema_two",
        lambda: _mutated(lambda d: d.__setitem__("schema_version", 2)),
        "schema_version",
        "unsupported schema_version 2 (expected 1)",
    ),
    (
        "description_empty",
        lambda: _mutated(lambda d: d.__setitem__("description", "")),
        "description",
        "description must be a non-empty string",
    ),
    (
        "contexts_not_dict",
        lambda: _mutated(lambda d: d.__setitem__("contexts", ["x"])),
        "contexts",
        "contexts must be a dict (got list)",
    ),
    (
        "contexts_unknown",
        lambda: _mutated(lambda d: d["contexts"].__setitem__("bogus", "x")),
        "contexts",
        "unknown context(s): bogus",
    ),
    (
        "contexts_missing",
        lambda: _mutated(lambda d: d["contexts"].pop("publish")),
        "contexts",
        "incomplete contexts: missing publish",
    ),
    (
        "context_description_empty",
        lambda: _mutated(lambda d: d["contexts"].__setitem__("hosted", "")),
        "contexts.hosted",
        "context 'hosted' description must be a non-empty string",
    ),
    (
        "gates_not_list",
        lambda: _mutated(lambda d: d.__setitem__("gates", {})),
        "gates",
        "gates must be a list (got dict)",
    ),
    (
        "gates_empty",
        lambda: _mutated(lambda d: d.__setitem__("gates", [])),
        "gates",
        "gates must be a non-empty list",
    ),
    (
        "gate_not_dict",
        lambda: _mutated(lambda d: d.__setitem__("gates", ["x"])),
        "gates[0]",
        "gate at index 0 must be a JSON object (got str)",
    ),
    (
        "gate_unknown_key",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("extra", 1)),
        "gates[0]",
        "unknown key(s) in gate[0]: extra",
    ),
    (
        "gate_missing_key",
        lambda: _mutated(lambda d: d["gates"][0].pop("required_contexts")),
        "gates[0]",
        "missing required key(s) in gate[0]: required_contexts",
    ),
    (
        "gate_id_empty",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("id", "")),
        "gates[0].id",
        "gate[0].id must be a non-empty string",
    ),
    (
        "gate_id_unsafe",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("id", "bad id!")),
        "gates[0].id",
        "gate[0].id 'bad id!' contains unsafe characters",
    ),
    (
        "gate_id_duplicate",
        lambda: _mutated(lambda d: d.__setitem__("gates", [_gate(), _gate()])),
        "gates[1].id",
        "duplicate gate id: 'gate-a'",
    ),
    (
        "gate_description_empty",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("description", "")),
        "gates[0].description",
        "gate[0] (gate-a).description must be a non-empty string",
    ),
    (
        "rc_not_list",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("required_contexts", "hosted")),
        "gates[0].required_contexts",
        "gate[0] (gate-a).required_contexts must be a list",
    ),
    (
        "rc_empty",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("required_contexts", [])),
        "gates[0].required_contexts",
        "gate[0] (gate-a).required_contexts must be a non-empty list",
    ),
    (
        "rc_non_string",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("required_contexts", [1])),
        "gates[0].required_contexts",
        "gate[0] (gate-a).required_contexts contains non-string: 1",
    ),
    (
        "rc_unknown",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("required_contexts", ["bogus"])),
        "gates[0].required_contexts",
        "gate[0] (gate-a).required_contexts contains unknown context: 'bogus'",
    ),
    (
        "rc_duplicate",
        lambda: _mutated(
            lambda d: d["gates"][0].__setitem__("required_contexts", ["hosted", "hosted"])
        ),
        "gates[0].required_contexts",
        "gate[0] (gate-a).required_contexts contains duplicate context: 'hosted'",
    ),
    (
        "bindings_not_dict",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("bindings", ["x"])),
        "gates[0].bindings",
        "gate[0] (gate-a).bindings must be a dict",
    ),
    (
        "bindings_unknown_key",
        lambda: _mutated(lambda d: d["gates"][0]["bindings"].__setitem__("extra", 1)),
        "gates[0].bindings",
        "gate[0] (gate-a).bindings contains unknown key(s): extra",
    ),
    (
        "make_target_int",
        lambda: _mutated(lambda d: d["gates"][0]["bindings"].__setitem__("make_target", 3)),
        "gates[0].bindings.make_target",
        "gate[0] (gate-a).bindings.make_target must be a string or null (got int)",
    ),
    (
        "make_target_null_string",
        lambda: _mutated(lambda d: d["gates"][0]["bindings"].__setitem__("make_target", "null")),
        "gates[0].bindings.make_target",
        'gate[0] (gate-a).bindings.make_target must be JSON null, not the string "null"',
    ),
    (
        "stage_bool",
        lambda: _mutated(lambda d: d["gates"][0]["bindings"].__setitem__("local_ci_stage", True)),
        "gates[0].bindings.local_ci_stage",
        "gate[0] (gate-a).bindings.local_ci_stage must be an integer or null (got bool)",
    ),
    (
        "make_target_collision",
        lambda: _mutated(
            lambda d: d.__setitem__(
                "gates",
                [
                    _gate(),
                    _second_gate(
                        bindings={
                            "make_target": "check-a",
                            "ci_job": "job-b",
                            "local_ci_stage": None,
                        }
                    ),
                ],
            )
        ),
        "gates[1].bindings.make_target",
        "make_target 'check-a' already used by gate 'gate-a'",
    ),
    (
        "ci_job_collision",
        lambda: _mutated(
            lambda d: d.__setitem__(
                "gates",
                [
                    _gate(),
                    _second_gate(
                        bindings={
                            "make_target": "check-b",
                            "ci_job": "job-a",
                            "local_ci_stage": None,
                        }
                    ),
                ],
            )
        ),
        "gates[1].bindings.ci_job",
        "ci_job 'job-a' already used by gate 'gate-a'",
    ),
    (
        "recipe_not_list",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("make_recipe", "echo hi")),
        "gates[0].make_recipe",
        "gate[0] (gate-a).make_recipe must be a list of recipe-line strings",
    ),
    (
        "recipe_empty",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("make_recipe", [])),
        "gates[0].make_recipe",
        "gate[0] (gate-a).make_recipe must be a non-empty list",
    ),
    (
        "recipe_line_not_string",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("make_recipe", [1])),
        "gates[0].make_recipe[0]",
        "gate[0] (gate-a).make_recipe[0] must be a non-empty string",
    ),
    (
        "recipe_line_untrimmed",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("make_recipe", ["  echo hi  "])),
        "gates[0].make_recipe[0]",
        "gate[0] (gate-a).make_recipe[0] must be one whitespace-trimmed recipe line",
    ),
    (
        "recipe_line_newline",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("make_recipe", ["echo hi\n"])),
        "gates[0].make_recipe[0]",
        "gate[0] (gate-a).make_recipe[0] must be one whitespace-trimmed recipe line",
    ),
    (
        "recipe_without_target",
        lambda: _mutated(
            lambda d: (
                d["gates"][0].__setitem__(
                    "bindings", {"make_target": None, "ci_job": "job-a", "local_ci_stage": None}
                ),
                d["gates"][0].__setitem__("make_recipe", ["echo hi"]),
            )
        ),
        "gates[0].make_recipe",
        "gate[0] (gate-a).make_recipe requires a string make_target binding",
    ),
    (
        "local_without_target",
        lambda: _mutated(
            lambda d: (
                d["gates"][0].__setitem__("required_contexts", ["local-serial"]),
                d["gates"][0]["bindings"].__setitem__("make_target", None),
            )
        ),
        "gates[0].bindings.make_target",
        "gate[0] (gate-a) declares local context(s) local-serial but has no Make target "
        "for the local runner",
    ),
    (
        "local_stage_outside",
        lambda: _mutated(
            lambda d: (
                d["gates"][0].__setitem__("required_contexts", ["local-serial"]),
                d["gates"][0]["bindings"].__setitem__("local_ci_stage", 9),
            )
        ),
        "gates[0].bindings.local_ci_stage",
        "gate[0] (gate-a) declares local context(s) local-serial but local_ci_stage 9 "
        "is outside the executable stages 3-7",
    ),
    (
        "depends_not_list",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("depends_on", "gate-b")),
        "gates[0].depends_on",
        "gate[0] (gate-a).depends_on must be a list",
    ),
    (
        "depends_entry_empty",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("depends_on", [""])),
        "gates[0].depends_on",
        "gate[0] (gate-a).depends_on entry must be a non-empty string",
    ),
    (
        "ti_not_list",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("trigger_inputs", "x")),
        "gates[0].trigger_inputs",
        "gate[0] (gate-a).trigger_inputs must be a list; trigger_inputs is the ordered, "
        "bidirectional E2E allowlist partition; it never controls whether a gate runs",
    ),
    (
        "ti_entry_empty",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("trigger_inputs", [""])),
        "gates[0].trigger_inputs[0]",
        "gate[0] (gate-a).trigger_inputs[0] must be a non-empty string; trigger_inputs is "
        "the ordered, bidirectional E2E allowlist partition; it never controls whether a gate runs",
    ),
    (
        "ti_unsafe_path",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("trigger_inputs", ["../outside"])),
        "gates[0].trigger_inputs[0]",
        "gate[0] (gate-a).trigger_inputs[0] '../outside' contains unsafe characters; "
        "trigger_inputs is the ordered, bidirectional E2E allowlist partition; it never "
        "controls whether a gate runs",
    ),
    (
        "ti_duplicate",
        lambda: _mutated(
            lambda d: d["gates"][0].__setitem__("trigger_inputs", ["a/b.py", "a/b.py"])
        ),
        "gates[0].trigger_inputs[1]",
        "gate[0] (gate-a).trigger_inputs contains duplicate path: 'a/b.py'; trigger_inputs "
        "is the ordered, bidirectional E2E allowlist partition; it never controls whether "
        "a gate runs",
    ),
    (
        "depends_self",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("depends_on", ["gate-a"])),
        "gates.gate-a.depends_on",
        "gate 'gate-a' depends on itself",
    ),
    (
        "depends_unknown",
        lambda: _mutated(lambda d: d["gates"][0].__setitem__("depends_on", ["gate-z"])),
        "gates.gate-a.depends_on",
        "gate 'gate-a' depends on unknown gate 'gate-z'",
    ),
    (
        "cycle_two",
        lambda: _mutated(
            lambda d: d.__setitem__(
                "gates",
                [
                    _gate(depends_on=["gate-b"]),
                    _second_gate(depends_on=["gate-a"]),
                ],
            )
        ),
        "gates.gate-a.depends_on",
        "circular dependency between 'gate-a' and 'gate-b'",
    ),
    (
        "cycle_three",
        lambda: _mutated(
            lambda d: d.__setitem__(
                "gates",
                [
                    _gate(depends_on=["gate-b"]),
                    _second_gate(depends_on=["gate-c"]),
                    _gate(
                        id="gate-c",
                        bindings={
                            "make_target": "check-c",
                            "ci_job": "job-c",
                            "local_ci_stage": None,
                        },
                        hosted={
                            "order": 3,
                            "display_name": "Gate C",
                            "check_step_name": "Run gate c",
                        },
                        depends_on=["gate-a"],
                    ),
                ],
            )
        ),
        "gates.gate-a.depends_on",
        "circular dependency among gates: 'gate-a', 'gate-b', 'gate-c' "
        "(gate-a -> gate-b -> gate-c -> gate-a)",
    ),
    ("valid", lambda: _registry(), "", ""),
)


def test_split_siblings_never_import_their_facade() -> None:
    """Siblings reach collaborators through defining siblings, never the facade."""
    for module_name, facade in SPLIT_SIBLINGS.items():
        module = __import__(module_name)
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] != facade, (module_name, node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] != facade, (module_name, node.lineno)


@pytest.mark.parametrize(
    ("case", "builder", "expected_path", "expected_message"),
    REGISTRY_FINDING_CASES,
    ids=[case for case, _, _, _ in REGISTRY_FINDING_CASES],
)
def test_registry_diagnostics_are_exact(
    case: str,
    builder: Callable[[], Any],
    expected_path: str,
    expected_message: str,
) -> None:
    """Schema diagnostics keep the pre-split message, path, and first-failure order."""
    data = builder()
    if case == "valid":
        assert check_gate_parity._validate_registry(data) == data["gates"]
        return
    with pytest.raises(schema.SchemaValidationError) as error:
        check_gate_parity._validate_registry(data)
    assert error.value.source == "registry"
    assert error.value.path == expected_path
    assert error.value.message == expected_message


def _tiny_gates() -> list[dict[str, Any]]:
    return [
        {
            "id": "check-alpha",
            "description": "Alpha gate",
            "required_contexts": ["local-serial"],
            "bindings": {"make_target": "check-alpha", "ci_job": None, "local_ci_stage": 3},
            "make_recipe": ["echo alpha"],
        },
        {
            "id": "check-beta",
            "description": "Beta gate",
            "required_contexts": ["local-serial"],
            "bindings": {"make_target": "check-beta", "ci_job": None, "local_ci_stage": 4},
            "make_recipe": ["echo beta", "echo done"],
        },
        {
            "id": "check-gate-suites",
            "description": "Suites gate",
            "required_contexts": ["local-serial"],
            "bindings": {"make_target": "check-gate-suites", "ci_job": None, "local_ci_stage": 7},
        },
    ]


def test_generated_make_include_is_exact() -> None:
    """The generated Make include is byte-identical to the pre-split capture."""
    assert sync_ci_gate_jobs._render_make_include(_tiny_gates()) == (
        "# Generated by scripts/sync_ci_gate_jobs.py from scripts/gate_registry.json.\n"
        "# Do not edit by hand; `make check` fails when this file is not current.\n"
        "# Refresh with `poetry run python scripts/sync_ci_gate_jobs.py --write`.\n"
        "\n"
        ".PHONY: check-alpha check-beta\n"
        "\n"
        "# Alpha gate\n"
        "check-alpha:\n"
        "\techo alpha\n"
        "\n"
        "# Beta gate\n"
        "check-beta:\n"
        "\techo beta\n"
        "\techo done\n"
    )


def test_generated_docs_table_is_exact() -> None:
    """The gate-roster docs region is byte-identical to the pre-split capture."""
    docs_text = f"before\n{DOCS_TABLE_BEGIN}\nold\n{DOCS_TABLE_END}\nafter\n"
    assert sync_ci_gate_jobs.expected_docs_text(docs_text, _tiny_gates()) == (
        "before\n"
        "<!-- BEGIN GENERATED: gate-registry-table -->\n"
        "| Gate | Make target | Contexts | Local stage | Hosted job |\n"
        "|---|---|---|---|---|\n"
        "| `check-alpha` | `make check-alpha` | local-serial | 3 | — |\n"
        "| `check-beta` | `make check-beta` | local-serial | 4 | — |\n"
        "| `check-gate-suites` | `make check-gate-suites` | local-serial | 7 | — |\n"
        "<!-- END GENERATED: gate-registry-table -->\n"
        "after\n"
    )


def test_e2e_paths_and_make_targets_are_exact() -> None:
    """The flattened E2E allowlist and parse-time target list keep their order."""
    e2e_gates = [
        {
            "id": "gate-one",
            "required_contexts": ["e2e-trigger"],
            "trigger_inputs": ["a.py", "b.py"],
        },
        {"id": "gate-two", "required_contexts": ["e2e-trigger"], "trigger_inputs": ["c.py"]},
        {"id": "gate-three", "required_contexts": ["local-serial"], "trigger_inputs": []},
    ]
    assert sync_ci_gate_jobs._expected_e2e_paths(e2e_gates) == ("a.py", "b.py", "c.py")
    assert sync_ci_gate_jobs._check_gate_targets(_tiny_gates()) == (
        "check-alpha check-beta check-gate-suites"
    )


def test_generator_diagnostics_are_exact() -> None:
    """Generator fail-closed diagnostics match the pre-split captures exactly."""
    registry = sync_ci_gate_jobs._parse_registry(sync_ci_gate_jobs.DEFAULT_REGISTRY)
    workflow = sync_ci_gate_jobs.DEFAULT_WORKFLOW.read_text(encoding="utf-8")
    e2e = sync_ci_gate_jobs.DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8")
    publish = sync_ci_gate_jobs.DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.expected_workflow_text(workflow.replace(f"{JOB_END}\n", "", 1), registry)
    assert str(error.value) == "ci.yml: generated marker pairs are incomplete or duplicated"

    marker = workflow.index(JOB_BEGIN)
    wrong_action = workflow[:marker] + workflow[marker:].replace(
        sync_ci_gate_jobs.CHECKOUT_REF, f"actions/cache@{'1' * 40}", 1
    )
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.expected_workflow_text(wrong_action, registry)
    assert str(error.value) == "ci.yml: jobs.module-core-compat action versions/ordering drifted"

    changed = workflow.replace("        fetch-depth: 0\n", "", 1)
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.expected_workflow_text(changed, registry)
    assert str(error.value) == "ci.yml: jobs.commit-testimony-gate checkout step drifted"

    stale = workflow[:marker] + workflow[marker:].replace(
        sync_ci_gate_jobs.CHECKOUT_REF, f"actions/checkout@{'0' * 40}", 1
    )
    assert stale != workflow
    assert sync_ci_gate_jobs.expected_workflow_text(stale, registry) == workflow

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.expected_e2e_workflow_text(
            e2e.replace(f"{E2E_PATHS_END}\n", "", 1), registry
        )
    assert str(error.value) == "e2e.yml: generated marker pair is incomplete or duplicated"

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.expected_publish_workflow_text(
            publish.replace(f"{PUBLISH_END}\n", "", 1), registry
        )
    assert str(error.value) == "publish.yml: generated marker pair is incomplete or duplicated"

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs._generated_make_targets(
            [
                {
                    "id": "check-gamma",
                    "description": "Gamma gate",
                    "required_contexts": ["local-serial"],
                    "bindings": {
                        "make_target": "check-gamma",
                        "ci_job": None,
                        "local_ci_stage": 5,
                    },
                }
            ]
        )
    assert str(error.value) == (
        "gate 'check-gamma': make_target 'check-gamma' has no make_recipe and is not "
        "a declared hand-owned Makefile target"
    )

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs._generated_make_targets(
            [
                {
                    "id": "check-gate-suites",
                    "description": "Suites",
                    "required_contexts": ["local-serial"],
                    "bindings": {
                        "make_target": "check-gate-suites",
                        "ci_job": None,
                        "local_ci_stage": 7,
                    },
                    "make_recipe": ["echo suites"],
                }
            ]
        )
    assert str(error.value) == (
        "gate 'check-gate-suites': declares both a make_recipe and a hand-owned exemption"
    )


def test_e2e_duplicate_path_claim_diagnostic_is_exact(tmp_path: Path) -> None:
    """A path claimed by two gates fails closed with the pre-split message."""
    data = json.loads(sync_ci_gate_jobs.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    owner = next(gate for gate in data["gates"] if gate["trigger_inputs"])
    duplicate = dict(owner)
    duplicate["id"] = "gate-dup"
    duplicate["bindings"] = {
        "make_target": "check-dup",
        "ci_job": None,
        "local_ci_stage": None,
    }
    duplicate["required_contexts"] = ["e2e-trigger"]
    duplicate.pop("hosted", None)
    duplicate.pop("publish", None)
    duplicate.pop("local", None)
    duplicate.pop("makefile_help", None)
    duplicate["depends_on"] = []
    duplicate["trigger_inputs"] = [owner["trigger_inputs"][0]]
    data["gates"].append(duplicate)
    registry_path = tmp_path / "registry_dup.json"
    registry_path.write_text(json.dumps(data), encoding="utf-8")
    gates = sync_ci_gate_jobs._parse_registry(registry_path)
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs._expected_e2e_paths(gates)
    assert str(error.value) == (
        f"e2e trigger path {owner['trigger_inputs'][0]!r} is claimed by both "
        f"{owner['id']!r} and 'gate-dup'; the allowlist partition admits one owner per path"
    )


def test_parse_diagnostics_are_exact(tmp_path: Path) -> None:
    """Loader diagnostics keep their pre-split wording and embedded paths."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs._parse_registry(bad_json)
    assert str(error.value) == (
        f"{bad_json}: JSON parse error: Expecting property name enclosed in double "
        "quotes: line 1 column 2 (char 1)"
    )

    missing = tmp_path / "missing.json"
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs._parse_registry(missing)
    assert str(error.value) == (
        f"cannot read registry {missing}: [Errno 2] No such file or directory: '{missing}'"
    )

    duplicate = sync_ci_gate_jobs.DEFAULT_WORKFLOW.read_text(encoding="utf-8").replace(
        "name: CI\n", "name: CI\nname: Duplicate\n", 1
    )
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs._parse_workflow(duplicate, "fixture ci.yml")
    assert str(error.value) == "fixture ci.yml: Duplicate YAML key: 'name'"


def test_unreadable_source_diagnostics_are_exact(tmp_path: Path) -> None:
    """Missing generated-source inputs keep their pre-split read diagnostics."""
    missing = tmp_path / "missing.yml"
    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.sync_workflow(missing)
    assert str(error.value) == (
        f"cannot read workflow {missing}: [Errno 2] No such file or directory: '{missing}'"
    )

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.sync_e2e_workflow(missing)
    assert str(error.value) == (
        f"cannot read E2E workflow {missing}: [Errno 2] No such file or directory: '{missing}'"
    )

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.sync_publish_workflow(missing)
    assert str(error.value) == (
        f"cannot read workflow {missing}: [Errno 2] No such file or directory: '{missing}'"
    )

    with pytest.raises(sync_ci_gate_jobs.GeneratorError) as error:
        sync_ci_gate_jobs.sync_docs_table(missing)
    assert str(error.value) == f"cannot read docs table file {missing}"


def test_pinned_catalog_constants_stay_single_literal_assignments() -> None:
    """The action-pin refresher edits these exact lines; keep one assignment each."""
    source = Path(sync_ci_gate_jobs.__file__).read_text(encoding="utf-8")
    for name in (
        "CHECKOUT_REF",
        "CHECKOUT_COMMENT",
        "SETUP_PYTHON_REF",
        "SETUP_PYTHON_COMMENT",
        "INSTALL_POETRY_REF",
        "INSTALL_POETRY_COMMENT",
    ):
        assert source.count(f"{name} = ") == 1, name
