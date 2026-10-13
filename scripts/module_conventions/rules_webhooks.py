"""
Rule 26's inbound-webhook checks and their verification mechanics.

The mechanics live in private sibling modules (``_webhooks_routes``,
``_webhooks_views``, ``_webhooks_services``, ``_webhooks_signature``,
``_webhooks_flows``); this module orchestrates rule 26's ordered findings and
re-exports every moved name so existing import paths and attribute lookups
keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``Callable``, ``Mapping``, ``Corpus``, and core's private helpers);
# the redundant aliases keep every one importable from this facade.
import ast as ast
from collections.abc import Callable as Callable
from collections.abc import Mapping as Mapping

from scripts.module_conventions._webhooks_flows import (
    _is_rejection_value,
    _may_return_any,
    _may_return_non_rejection,
    _overwritten_names,
    _rejects_by_raising,
    _rejects_failure,
)
from scripts.module_conventions._webhooks_routes import _route_entries
from scripts.module_conventions._webhooks_services import (
    _callee_signature_binding,
    _direct_call_node,
    _entry_signature_binding,
    _executed_local_calls,
    _executed_service_calls,
    _meaningful_verification,
    _mentions_headers,
    _request_header_argument,
    _service_call_target,
    _service_verifies_signature,
)
from scripts.module_conventions._webhooks_signature import (
    CANDIDATE_SELECTION_METHODS,
    CANDIDATE_SPLIT_METHODS,
    SIGNATURE_METHOD_DERIVATIONS,
    _and_evaluated_compares,
    _calls_construct_event,
    _candidate_guard_returns,
    _candidate_value,
    _consumes_names,
    _distinct_arguments,
    _evaluated_signature_value,
    _failure_branch,
    _signature_candidate_loop_verifies,
    _single_target_names,
    _update_candidate_derivation,
    _verification_on_accepting_path,
)
from scripts.module_conventions._webhooks_views import _view_violations
from scripts.module_conventions.core import (
    Corpus,
)
from scripts.module_conventions.core import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions.core import (
    _class_names as _class_names,
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
    _static_truth as _static_truth,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "CANDIDATE_SELECTION_METHODS",
    "CANDIDATE_SPLIT_METHODS",
    "SIGNATURE_METHOD_DERIVATIONS",
    "_and_evaluated_compares",
    "_callee_signature_binding",
    "_calls_construct_event",
    "_candidate_guard_returns",
    "_candidate_value",
    "_consumes_names",
    "_direct_call_node",
    "_distinct_arguments",
    "_entry_signature_binding",
    "_evaluated_signature_value",
    "_executed_local_calls",
    "_executed_service_calls",
    "_failure_branch",
    "_is_rejection_value",
    "_may_return_any",
    "_may_return_non_rejection",
    "_meaningful_verification",
    "_mentions_headers",
    "_overwritten_names",
    "_rejects_by_raising",
    "_rejects_failure",
    "_request_header_argument",
    "_service_call_target",
    "_service_verifies_signature",
    "_signature_candidate_loop_verifies",
    "_single_target_names",
    "_update_candidate_derivation",
    "_verification_on_accepting_path",
    "rule_26_webhooks",
)


def rule_26_webhooks(corpus: Corpus) -> list[str]:
    """Rule 26: webhook routes mount APIViews that verify the incoming signature."""
    violations: list[str] = []
    for module in corpus.modules:
        urls = module.files.get("urls.py")
        if urls is None:
            continue
        view_names, route_violations = _route_entries(module.name, urls)
        violations.extend(route_violations)
        for view_name in view_names:
            violations.extend(_view_violations(module, view_name))
    return violations
