"""
Behavioral controls for the ``rules_docs`` split (SA267).

Rule 38's README mechanics live in the private sibling (``_docs_readme``)
behind the ``rules_docs`` facade.  SA267 has closed, so SA279 retired the
pre-split surface pins; these controls keep the split's structural invariants
and the exact ordered findings of representative corpora captured from the
pre-split module, so a later change cannot silently drop, reorder, or reword
them.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _docs_readme,
    rules_docs,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    GOLDEN_README,
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_docs_readme": _docs_readme,
}


def _without_readme(name: str = "demo") -> Module:
    module = _golden_module(name)
    return replace(
        module,
        root_files={key: value for key, value in module.root_files.items() if key != "README.md"},
    )


def _with_readme(readme: str, name: str = "demo") -> Module:
    module = _golden_module(name)
    return replace(module, root_files={**module.root_files, "README.md": readme})


def _with_report_command(command: str, readme: str = GOLDEN_README) -> Module:
    module = _with_files(
        _golden_module(),
        **{"management/commands/quickscale_demo_report.py": command},
    )
    return replace(module, root_files={**module.root_files, "README.md": readme})


def _role_views() -> str:
    return (
        "from quickscale_modules_orgs.permissions import OrgRoleMixin\n\n"
        "class DashboardView(OrgRoleMixin):\n"
        "    min_org_role = 'viewer'\n"
    )


def _role_views_with_surface(surface: str) -> Module:
    module = _with_files(_golden_module(), views=_role_views())
    return replace(
        module,
        root_files={**module.root_files, "README.md": GOLDEN_README.replace("Nothing.", surface)},
    )


def _manifest_without_config() -> Module:
    module = _golden_module()
    manifest = {key: value for key, value in module.manifest.items() if key != "config"}
    return replace(module, manifest=manifest)


def _manifest_with_config(config: object) -> Module:
    module = _golden_module()
    return replace(module, manifest={**module.manifest, "config": config})


def _all_checks_failing() -> Module:
    readme = GOLDEN_README.replace("`api_rate_limit` - throttle rate.", "")
    readme = readme.replace("## Operations", "## 2.0 Notes\n\n## Operations")
    readme = readme.replace("## Operations\nNone.\n", "")
    module = _with_files(
        _golden_module(),
        views=_role_views(),
        **{
            "management/commands/quickscale_demo_extra.py": (
                "class Command:\n    def handle(self, *args, **options):\n        return None\n"
            )
        },
    )
    return replace(module, root_files={**module.root_files, "README.md": readme})


CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "missing_readme": lambda: _corpus(_without_readme()),
    "missing_heading": lambda: _corpus(
        _with_readme(GOLDEN_README.replace("## Operations\nNone.\n", ""))
    ),
    "out_of_order_heading": lambda: _corpus(
        _with_readme("## Extending\nNone.\n\n" + GOLDEN_README.replace("## Extending\nNone.\n", ""))
    ),
    "versioned_heading": lambda: _corpus(
        _with_readme(
            GOLDEN_README.replace("## Operations", "## 1.2 Notes\nSome notes.\n\n## Operations")
        )
    ),
    "config_option_missing": lambda: _corpus(
        _with_readme(GOLDEN_README.replace("`api_rate_limit` - throttle rate.", ""))
    ),
    "manifest_without_config": lambda: _corpus(_manifest_without_config()),
    "manifest_config_not_mapping": lambda: _corpus(_manifest_with_config("broken")),
    "non_string_option_key": lambda: _corpus(
        _manifest_with_config(
            {
                "mutable": {1: {"type": "string"}},
                "immutable": {},
            }
        )
    ),
    "command_missing": lambda: _corpus(
        _with_files(
            _golden_module(),
            **{
                "management/commands/quickscale_demo_extra.py": (
                    "class Command:\n    def handle(self, *args, **options):\n        return None\n"
                )
            },
        )
    ),
    "command_init_skipped": lambda: _corpus(
        _with_files(_golden_module(), **{"management/commands/__init__.py": ""})
    ),
    "command_private_skipped": lambda: _corpus(
        _with_files(
            _golden_module(),
            **{"management/commands/_support.py": "def seed():\n    return None\n"},
        )
    ),
    "command_flag_missing": lambda: _corpus(
        _with_report_command(
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--format', choices=('human', 'json'))\n",
            GOLDEN_README.replace(
                "- `quickscale_demo_run`.",
                "- `quickscale_demo_run`.\n- `quickscale_demo_report`.",
            ),
        )
    ),
    "command_flag_documented": lambda: _corpus(
        _with_report_command(
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--format', choices=('human', 'json'))\n",
            GOLDEN_README.replace(
                "- `quickscale_demo_run`.",
                "- `quickscale_demo_run`.\n- `quickscale_demo_report --format`.",
            ),
        )
    ),
    "command_flag_positional_skipped": lambda: _corpus(
        _with_report_command(
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('snapshot_id')\n",
            GOLDEN_README.replace(
                "- `quickscale_demo_run`.",
                "- `quickscale_demo_run`.\n- `quickscale_demo_report`.",
            ),
        )
    ),
    "command_flag_private_skipped": lambda: _corpus(
        _with_files(
            _golden_module(),
            **{
                "management/commands/_support.py": (
                    "def add_flags(parser):\n    parser.add_argument('--hidden')\n"
                )
            },
        )
    ),
    "role_required": lambda: _corpus(_role_views_with_surface("Nothing.")),
    "role_documented_inline": lambda: _corpus(_role_views_with_surface("Minimum role: `viewer`.")),
    "role_documented_table": lambda: _corpus(
        _role_views_with_surface("| Role | Behavior |\n|------|----------|\n| `member` | reads |")
    ),
    "two_modules_order": lambda: _corpus(
        _with_readme(GOLDEN_README.replace("## Operations\nNone.\n", "")),
        _without_readme("blog"),
    ),
    "all_checks_failing": lambda: _corpus(_all_checks_failing()),
}

#: (case, expected findings) captured from the pre-split module; each list is
#: exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", ()),
    ("missing_readme", ("rule 38: demo: README.md is missing",)),
    ("missing_heading", ("rule 38: demo: README heading 'Operations' missing",)),
    ("out_of_order_heading", ("rule 38: demo: README heading 'Extending' missing",)),
    ("versioned_heading", ("rule 38: demo: README heading '1.2 Notes' has a version",)),
    (
        "config_option_missing",
        ("rule 38: demo: Configuration does not name option 'api_rate_limit'",),
    ),
    ("manifest_without_config", ()),
    ("manifest_config_not_mapping", ()),
    ("non_string_option_key", ()),
    (
        "command_missing",
        ("rule 38: demo: Management commands does not name 'quickscale_demo_extra'",),
    ),
    ("command_init_skipped", ()),
    ("command_private_skipped", ()),
    (
        "command_flag_missing",
        ("rule 38: demo: Management commands does not name flag '--format'",),
    ),
    ("command_flag_documented", ()),
    ("command_flag_positional_skipped", ()),
    ("command_flag_private_skipped", ()),
    ("role_required", ("rule 38: demo: Public surface does not list the minimum role",)),
    ("role_documented_inline", ()),
    ("role_documented_table", ()),
    (
        "two_modules_order",
        (
            "rule 38: demo: README heading 'Operations' missing",
            "rule 38: blog: README.md is missing",
        ),
    ),
    (
        "all_checks_failing",
        (
            "rule 38: demo: README heading 'Operations' missing",
            "rule 38: demo: README heading '2.0 Notes' has a version",
            "rule 38: demo: Configuration does not name option 'api_rate_limit'",
            "rule 38: demo: Management commands does not name 'quickscale_demo_extra'",
            "rule 38: demo: Public surface does not list the minimum role",
        ),
    ),
)


def test_rule_37_exempts_only_the_facade() -> None:
    """The split sibling stays inside rule 37's closed world."""
    assert (
        "scripts",
        "module_conventions/rules_docs.py",
    ) in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in RULE_37_ALLOWED_LITERAL_FILES


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_docs", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_docs", "registry"}, (
                        name,
                        node.lineno,
                    )


@pytest.mark.parametrize(
    ("case", "expected"),
    EXACT_FINDINGS,
    ids=[case for case, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(case: str, expected: tuple[str, ...]) -> None:
    assert rules_docs.rule_38_readme_content(CASE_BUILDERS[case]()) == list(expected)
