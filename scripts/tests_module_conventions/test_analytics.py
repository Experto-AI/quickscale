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


def test_session_key_attribute_read_is_reported() -> None:
    """Reading the session credential in module source violates rule 22."""
    module = _with_files(
        _golden_module(),
        **{
            "services.py": (
                '"""Demo service surface."""\n\n'
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query(*, session):\n"
                "    return f'session:{session.session_key}'\n"
            ),
        },
    )
    violations = _violations(checker.rule_22_analytics_events, module)
    assert any("session_key" in violation for violation in violations)


def test_session_key_getattr_read_is_reported() -> None:
    """The getattr spelling of the session credential read is reported too."""
    module = _with_files(
        _golden_module(),
        **{
            "services.py": (
                '"""Demo service surface."""\n\n'
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query(*, session):\n"
                "    return getattr(session, 'session_key', None)\n"
            ),
        },
    )
    violations = _violations(checker.rule_22_analytics_events, module)
    assert any("session_key" in violation for violation in violations)


def test_migration_session_key_read_is_reported() -> None:
    """A migration logging the session credential is reported like any module source."""
    module = _with_files(
        _golden_module(),
        **{
            "migrations/0001_initial.py": (
                '"""Demo migration."""\n\n'
                "def cleanup(apps, schema_editor):\n"
                "    session = object()\n"
                "    logger.info('Removing session %s', session.session_key)\n"
            ),
        },
    )
    violations = _violations(checker.rule_22_analytics_events, module)
    assert any("session_key" in violation for violation in violations)


def test_random_anonymous_id_passes_the_session_key_clause() -> None:
    """A session-stored random anonymous ID reads no credential and passes."""
    module = _with_files(
        _golden_module(),
        **{
            "services.py": (
                '"""Demo service surface."""\n\n'
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query(*, session):\n"
                "    anonymous_id = session.get('quickscale_demo:anonymous_id')\n"
                "    if not anonymous_id:\n"
                "        anonymous_id = 'generated'\n"
                "        session['quickscale_demo:anonymous_id'] = anonymous_id\n"
                "    return anonymous_id\n"
            ),
        },
    )
    assert _violations(checker.rule_22_analytics_events, module) == []
