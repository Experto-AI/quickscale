"""
Analytics event rule.

The mechanics live in private sibling modules (``_analytics_events`` and
``_analytics_session_keys``); this module orchestrates rule 22 and re-exports
every moved name so existing import paths and the rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``Any``, and core's helpers); the redundant aliases keep every one
# importable from this facade.
import ast as ast
from typing import Any as Any

from scripts.module_conventions._analytics_events import (
    _capture_surface_violations,
    _event_stem_scan_violations,
)
from scripts.module_conventions._analytics_session_keys import (
    _names_session_key,
    _session_key_scan_violations,
    _session_key_violations,
)
from scripts.module_conventions.core import (
    Corpus,
)
from scripts.module_conventions.core import (
    Module as Module,
)
from scripts.module_conventions.core import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions.core import (
    _docstring_nodes as _docstring_nodes,
)
from scripts.module_conventions.core import (
    _keyword as _keyword,
)
from scripts.module_conventions.core import (
    _literal as _literal,
)
from scripts.module_conventions.core import (
    _parse as _parse,
)
from scripts.module_conventions.core import (
    _string_assignments as _string_assignments,
)
from scripts.module_conventions.core import (
    _string_list as _string_list,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "_names_session_key",
    "_session_key_violations",
    "rule_22_analytics_events",
)


def rule_22_analytics_events(corpus: Corpus) -> list[str]:
    """
    Rule 22: analytics events go through the module's one capture helper.

    The statically checkable clauses: ``analytics`` publishes exactly one
    ``capture_`` helper, ``capture_event``, and exports it from
    ``services.__all__``; no module source reads or names the session
    credential; every other module's ``capture_event`` call names an event
    whose string carries the calling module's ``quickscale_<module>_`` stem
    (``$pageview`` excepted).
    """
    return [
        *_capture_surface_violations(corpus),
        *_session_key_scan_violations(corpus),
        *_event_stem_scan_violations(corpus),
    ]
