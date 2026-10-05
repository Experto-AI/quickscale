"""Control cases for the analytics module-convention rules."""

from __future__ import annotations

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Module
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
)


def test_analytics_helper_control() -> None:
    analytics = Module(
        name="analytics",
        manifest={
            "name": "analytics",
            "config": {"mutable": {}, "immutable": {}},
            "dependencies": [],
        },
        files={
            "services.py": (
                "def capture_event(**kwargs):\n    return None\n\n"
                "def capture_pageview(**kwargs):\n    return None\n\n"
                "__all__ = ['capture_event', 'capture_pageview']\n"
            ),
        },
        root_files={},
        tests={},
    )
    assert _violations(checker.rule_22_analytics_events, analytics)


def test_analytics_event_name_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event(distinct_id='x', event='form_submit')\n"
        ),
    )
    violations = _violations(checker.rule_22_analytics_events, broken)
    assert any("stem" in violation for violation in violations)


def test_keyword_event_constant_control() -> None:
    module = _golden_module()
    services = 'DEMO_CREATED_EVENT: Final[str] = "quickscale_demo_created"\n'
    views = (
        "from quickscale_modules_demo.services import DEMO_CREATED_EVENT\n"
        "from quickscale_modules_analytics.services import capture_event\n\n"
        "def index():\n"
        "    capture_event(distinct_id='x', event=DEMO_CREATED_EVENT)\n"
    )
    good = _with_files(module, **{"services.py": services, "views.py": views})
    assert _violations(checker.rule_22_analytics_events, good) == []
    bad = _with_files(
        module,
        **{
            "services.py": services.replace("quickscale_demo_created", "created"),
            "views.py": views,
        },
    )
    assert any(
        "stem" in violation for violation in _violations(checker.rule_22_analytics_events, bad)
    )
