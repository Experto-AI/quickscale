"""
Parity controls for the ``rules_analytics`` split (SA267).

The capture-surface and event-stem mechanics and the session-credential scan
live in private siblings (``_analytics_events`` and
``_analytics_session_keys``) behind the ``rules_analytics`` facade.  These
controls pin the facade's preserved surface, the split's structural
invariants, and the exact ordered findings of representative corpora captured
from the pre-split module, so a later slice cannot silently drop, reorder, or
reword them.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _analytics_events,
    _analytics_session_keys,
    core,
    registry,
    rules_analytics,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_analytics_events": _analytics_events,
    "_analytics_session_keys": _analytics_session_keys,
}

FROZEN_SURFACE = (
    "_names_session_key",
    "_session_key_violations",
    "rule_22_analytics_events",
)

#: The pre-split module's own imports, which it exposed as module attributes;
#: the facade keeps every one importable through its redundant aliases.
FROZEN_IMPORTED_BINDINGS = (
    "Any",
    "Corpus",
    "Module",
    "_call_func_name",
    "_docstring_nodes",
    "_keyword",
    "_literal",
    "_parse",
    "_string_assignments",
    "_string_list",
    "ast",
)

FROZEN_CORE_HELPERS = (
    "Corpus",
    "Module",
    "_call_func_name",
    "_docstring_nodes",
    "_keyword",
    "_literal",
    "_parse",
    "_string_assignments",
    "_string_list",
)

FROZEN_SIGNATURES = {
    "_names_session_key": "(node: 'ast.AST') -> 'bool'",
    "_session_key_violations": (
        "(module: 'Module', tree: 'ast.Module', rel: 'str') -> 'list[str]'"
    ),
    "rule_22_analytics_events": "(corpus: 'Corpus') -> 'list[str]'",
}

ANALYTICS_GOOD_SERVICES = (
    "def capture_event(**kwargs):\n    return None\n\n__all__ = ['capture_event']\n"
)

SESSION_HEADER = '"""Demo service surface."""\n\n__all__ = ["demo_query"]\n\n\n'

TWO_MODULE_VIEWS = (
    "from quickscale_modules_analytics.services import capture_event\n\n"
    "def index(page):\n"
    "    page.session.session_key\n"
    "    capture_event(event='nope')\n"
)


def _analytics(services: str | None = ANALYTICS_GOOD_SERVICES) -> Module:
    """Build the analytics module; ``services=None`` removes services.py."""
    module = _golden_module("analytics")
    if services is None:
        return replace(
            module,
            files={key: value for key, value in module.files.items() if key != "services.py"},
        )
    return _with_files(module, services=services)


def _demo(**files: str) -> Module:
    return _with_files(_golden_module(), **files)


CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "surface_ok": lambda: _corpus(_analytics()),
    "surface_helpers": lambda: _corpus(
        _analytics(
            "def capture_event(**kwargs):\n    return None\n\n"
            "def capture_pageview(**kwargs):\n    return None\n\n"
            "__all__ = ['capture_event']\n"
        )
    ),
    "surface_exports": lambda: _corpus(
        _analytics(
            "def capture_event(**kwargs):\n    return None\n\n__all__ = ['capture_pageview']\n"
        )
    ),
    "surface_both": lambda: _corpus(
        _analytics(
            "def capture_event(**kwargs):\n    return None\n\n"
            "def capture_pageview(**kwargs):\n    return None\n\n"
            "__all__ = ['capture_pageview']\n"
        )
    ),
    "surface_no_services": lambda: _corpus(_analytics(None)),
    "session_attribute": lambda: _corpus(
        _demo(
            services=SESSION_HEADER
            + "def demo_query(*, session):\n"
            + "    return f'session:{session.session_key}'\n"
        )
    ),
    "session_getattr": lambda: _corpus(
        _demo(
            services=SESSION_HEADER
            + "def demo_query(*, session):\n"
            + "    return getattr(session, 'session_key', None)\n"
        )
    ),
    "session_docstring": lambda: _corpus(
        _demo(
            services=(
                '"""Demo service surface; never logs session_key."""\n\n'
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query():\n"
                "    return None\n"
            )
        )
    ),
    "session_name_and_string": lambda: _corpus(_demo(services='session_key = "session_key"\n')),
    "session_migration": lambda: _corpus(
        _demo(
            **{
                "migrations/0001_initial.py": (
                    '"""Demo migration."""\n\n'
                    "def cleanup(apps, schema_editor):\n"
                    "    session = object()\n"
                    "    logger.info('Removing session %s', session.session_key)\n"
                )
            }
        )
    ),
    "session_template_text": lambda: _corpus(
        _demo(**{"templates/quickscale_demo/base.html": "session_key\n"})
    ),
    "event_no_resolvable": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event(distinct_id='x')\n"
        )
    ),
    "event_name_unknown": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event(distinct_id='x', event=UNKNOWN_NAME)\n"
        )
    ),
    "event_stem_bad": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event(distinct_id='x', event='form_submit')\n"
        )
    ),
    "event_pageview": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event(distinct_id='x', event='$pageview')\n"
        )
    ),
    "event_constant_good": lambda: _corpus(
        _demo(
            services='DEMO_CREATED_EVENT: Final[str] = "quickscale_demo_created"\n',
            views=(
                "from quickscale_modules_demo.services import DEMO_CREATED_EVENT\n"
                "from quickscale_modules_analytics.services import capture_event\n\n"
                "def index():\n"
                "    capture_event(distinct_id='x', event=DEMO_CREATED_EVENT)\n"
            ),
        )
    ),
    "event_constant_bad": lambda: _corpus(
        _demo(
            services='DEMO_CREATED_EVENT: Final[str] = "created"\n',
            views=(
                "from quickscale_modules_demo.services import DEMO_CREATED_EVENT\n"
                "from quickscale_modules_analytics.services import capture_event\n\n"
                "def index():\n"
                "    capture_event(distinct_id='x', event=DEMO_CREATED_EVENT)\n"
            ),
        )
    ),
    "event_positional_good": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event('abc', 'quickscale_demo_x')\n"
        )
    ),
    "event_positional_bad": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event('abc', 'nope')\n"
        )
    ),
    "event_keyword_wins": lambda: _corpus(
        _demo(
            views="from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event('abc', 'nope', event='quickscale_demo_ok')\n"
        )
    ),
    "event_attribute_call": lambda: _corpus(
        _demo(
            views="from quickscale_modules import analytics\n\n"
            "def index():\n    analytics.capture_event(event='nope')\n"
        )
    ),
    "event_analytics_skipped": lambda: _corpus(
        _analytics(
            "def capture_event(**kwargs):\n    return None\n\n"
            "__all__ = ['capture_event']\n"
            "\n\ndef page():\n    capture_event(event='nope')\n"
        )
    ),
    "event_constant_cross_file": lambda: _corpus(
        _demo(
            **{
                "constants.py": 'DEMO_EVENT = "quickscale_demo_cross"\n',
                "views.py": (
                    "from quickscale_modules_demo.constants import DEMO_EVENT\n"
                    "from quickscale_modules_analytics.services import capture_event\n\n"
                    "def index():\n"
                    "    capture_event(distinct_id='x', event=DEMO_EVENT)\n"
                ),
            }
        )
    ),
    "event_two_modules_order": lambda: _corpus(
        _demo(views=TWO_MODULE_VIEWS),
        _with_files(_golden_module("blog"), views=TWO_MODULE_VIEWS),
    ),
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", "rule_22_analytics_events", ()),
    ("surface_ok", "rule_22_analytics_events", ()),
    (
        "surface_helpers",
        "rule_22_analytics_events",
        (
            "rule 22: analytics: capture helpers are ['capture_event', 'capture_pageview'], "
            "expected ['capture_event']",
        ),
    ),
    (
        "surface_exports",
        "rule_22_analytics_events",
        ("rule 22: analytics: capture_event is not in services.__all__",),
    ),
    (
        "surface_both",
        "rule_22_analytics_events",
        (
            "rule 22: analytics: capture helpers are ['capture_event', 'capture_pageview'], "
            "expected ['capture_event']",
            "rule 22: analytics: capture_event is not in services.__all__",
        ),
    ),
    ("surface_no_services", "rule_22_analytics_events", ()),
    (
        "session_attribute",
        "rule_22_analytics_events",
        (
            "rule 22: demo: services.py:7 uses session_key "
            "(a live session credential) in module source",
        ),
    ),
    (
        "session_getattr",
        "rule_22_analytics_events",
        (
            "rule 22: demo: services.py:7 uses session_key "
            "(a live session credential) in module source",
        ),
    ),
    ("session_docstring", "rule_22_analytics_events", ()),
    (
        "session_name_and_string",
        "rule_22_analytics_events",
        (
            "rule 22: demo: services.py:1 uses session_key "
            "(a live session credential) in module source",
            "rule 22: demo: services.py:1 uses session_key "
            "(a live session credential) in module source",
        ),
    ),
    (
        "session_migration",
        "rule_22_analytics_events",
        (
            "rule 22: demo: migrations/0001_initial.py:5 uses session_key "
            "(a live session credential) in module source",
        ),
    ),
    ("session_template_text", "rule_22_analytics_events", ()),
    (
        "event_no_resolvable",
        "rule_22_analytics_events",
        ("rule 22: demo: views.py calls capture_event with no resolvable event name",),
    ),
    (
        "event_name_unknown",
        "rule_22_analytics_events",
        ("rule 22: demo: views.py calls capture_event with no resolvable event name",),
    ),
    (
        "event_stem_bad",
        "rule_22_analytics_events",
        ("rule 22: demo: event 'form_submit' lacks the quickscale_demo_ stem",),
    ),
    ("event_pageview", "rule_22_analytics_events", ()),
    ("event_constant_good", "rule_22_analytics_events", ()),
    (
        "event_constant_bad",
        "rule_22_analytics_events",
        ("rule 22: demo: event 'created' lacks the quickscale_demo_ stem",),
    ),
    ("event_positional_good", "rule_22_analytics_events", ()),
    (
        "event_positional_bad",
        "rule_22_analytics_events",
        ("rule 22: demo: event 'nope' lacks the quickscale_demo_ stem",),
    ),
    ("event_keyword_wins", "rule_22_analytics_events", ()),
    (
        "event_attribute_call",
        "rule_22_analytics_events",
        ("rule 22: demo: event 'nope' lacks the quickscale_demo_ stem",),
    ),
    ("event_analytics_skipped", "rule_22_analytics_events", ()),
    ("event_constant_cross_file", "rule_22_analytics_events", ()),
    (
        "event_two_modules_order",
        "rule_22_analytics_events",
        (
            "rule 22: demo: views.py:4 uses session_key "
            "(a live session credential) in module source",
            "rule 22: blog: views.py:4 uses session_key "
            "(a live session credential) in module source",
            "rule 22: demo: event 'nope' lacks the quickscale_demo_ stem",
            "rule 22: blog: event 'nope' lacks the quickscale_blog_ stem",
        ),
    ),
)


def test_facade_publishes_the_pre_split_surface() -> None:
    """The facade's ``__all__`` is the pre-split module's own name set."""
    assert rules_analytics.__all__ == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert getattr(rules_analytics, name) is not None


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert rules_analytics.ast is ast
    assert rules_analytics.Any is Any
    for name in FROZEN_IMPORTED_BINDINGS:
        assert getattr(rules_analytics, name) is not None
    for name in FROZEN_CORE_HELPERS:
        assert getattr(rules_analytics, name) is getattr(core, name)


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    assert {
        name: str(inspect.signature(getattr(rules_analytics, name))) for name in FROZEN_SIGNATURES
    } == FROZEN_SIGNATURES


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert (
        "scripts",
        "module_conventions/rules_analytics.py",
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
                assert node.module.split(".")[-1] not in {"rules_analytics", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_analytics", "registry"}, (
                        name,
                        node.lineno,
                    )


def test_orchestrators_and_helpers_keep_their_homes() -> None:
    """Rule 22 stays orchestrated by the facade; the mechanics move out."""
    assert rules_analytics.rule_22_analytics_events.__module__ == (
        "scripts.module_conventions.rules_analytics"
    )
    assert rules_analytics._names_session_key is _analytics_session_keys._names_session_key
    assert (
        rules_analytics._session_key_violations is _analytics_session_keys._session_key_violations
    )
    for name in (
        "_analytics_module",
        "_capture_surface_violations",
        "_event_argument",
        "_event_constants",
        "_event_stem_findings",
        "_event_stem_scan_violations",
        "_module_event_violations",
        "_resolved_event",
    ):
        assert getattr(_analytics_events, name).__module__ == (
            "scripts.module_conventions._analytics_events"
        ), name
    for name in (
        "_names_session_key",
        "_session_key_scan_violations",
        "_session_key_violations",
    ):
        assert getattr(_analytics_session_keys, name).__module__ == (
            "scripts.module_conventions._analytics_session_keys"
        ), name


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registry's detector is the facade callable, not a sibling."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    assert detectors[22] is rules_analytics.rule_22_analytics_events
    assert checker.rule_22_analytics_events is rules_analytics.rule_22_analytics_events


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    assert getattr(rules_analytics, detector)(CASE_BUILDERS[case]()) == list(expected)
