"""
Parity controls for the ``rule_44`` split (SA268).

Rule 44's membership environment, expression scanner, and statement scanner
live in the private siblings (``_rule44_names``, ``_rule44_expressions``,
``_rule44_statements``) behind the ``rule_44`` facade.  These controls pin the
facade's preserved surface, the split's structural invariants, and the exact
ordered findings of representative corpora captured from the pre-split
module, so a later slice cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.module_conventions import (
    _rule44_expressions,
    _rule44_names,
    _rule44_statements,
    core,
    registry,
    rule_44,
)
from scripts.module_conventions._identity_module_lists import _module_list_violations
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    REPO_ROOT,
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_rule44_names": _rule44_names,
    "_rule44_expressions": _rule44_expressions,
    "_rule44_statements": _rule44_statements,
}

#: Every module-level name the pre-split ``rule_44`` published, from its own
#: ``def``/``class``/assignment statements.  The facade must keep exposing all
#: of them, private helpers, classes, and the type aliases included.
FROZEN_SURFACE = (
    "RULE_44_MEMBERSHIP_APP",
    "RULE_44_MEMBERSHIP_MODEL",
    "RULE_44_MEMBERSHIP_SOURCE",
    "RULE_44_QUERY_METHODS",
    "_RULE_44_ALIAS_PATHS",
    "_RULE_44_SOURCE_PARTS",
    "_Rule44DeferredBodies",
    "_Rule44Environment",
    "_Rule44Scope",
    "_rule_44_argument_names",
    "_rule_44_bind",
    "_rule_44_block_bindings",
    "_rule_44_bound_names",
    "_rule_44_call_violation",
    "_rule_44_definition_expressions",
    "_rule_44_expression_bindings",
    "_rule_44_membership_receiver",
    "_rule_44_names_membership_model",
    "_rule_44_pattern_names",
    "_rule_44_qualified_membership",
    "_rule_44_scan_block",
    "_rule_44_scan_expression",
    "_rule_44_scan_function",
    "_rule_44_scan_statement",
    "_rule_44_scope_declarations",
    "rule_44_role_checks",
)

#: The pre-split module's own imports, which it exposed as module attributes;
#: the facade keeps every one importable through its redundant aliases.
FROZEN_IMPORTED_BINDINGS = (
    "Corpus",
    "Mapping",
    "_attribute_chain",
    "_bound_names",
    "_call_func_name",
    "_keyword",
    "_literal",
    "_parse",
)

FROZEN_CORE_HELPERS = (
    "Corpus",
    "_attribute_chain",
    "_bound_names",
    "_call_func_name",
    "_keyword",
    "_literal",
    "_parse",
)

#: The pre-split signature of every callable the pre-split module published.
FROZEN_SIGNATURES = {
    "_Rule44Environment": (
        "(names: 'set[str] | None' = None, "
        "aliases: 'dict[str, frozenset[tuple[str, ...]]] | None' = None) -> 'None'"
    ),
    "_rule_44_argument_names": "(arguments: 'ast.arguments') -> 'set[str]'",
    "_rule_44_bind": (
        "(targets: 'list[ast.expr]', value: 'ast.expr', environment: '_Rule44Environment')"
        " -> 'None'"
    ),
    "_rule_44_block_bindings": "(statements: 'list[ast.stmt]') -> 'set[str]'",
    "_rule_44_bound_names": (
        "(function: 'ast.FunctionDef | ast.AsyncFunctionDef') -> 'frozenset[str]'"
    ),
    "_rule_44_call_violation": (
        "(call: 'ast.Call', environment: '_Rule44Environment', module_name: 'str', rel: 'str')"
        " -> 'str | None'"
    ),
    "_rule_44_definition_expressions": (
        "(node: 'ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef') -> 'list[ast.expr]'"
    ),
    "_rule_44_expression_bindings": "(expression: 'ast.expr') -> 'set[str]'",
    "_rule_44_membership_receiver": (
        "(node: 'ast.expr', environment: '_Rule44Environment') -> 'bool'"
    ),
    "_rule_44_names_membership_model": "(call: 'ast.Call') -> 'bool'",
    "_rule_44_pattern_names": "(pattern: 'ast.pattern') -> 'set[str]'",
    "_rule_44_qualified_membership": (
        "(chain: 'tuple[str, ...]', aliases: 'Mapping[str, frozenset[tuple[str, ...]]]') -> 'bool'"
    ),
    "_rule_44_scan_block": (
        "(statements: 'list[ast.stmt]', environment: '_Rule44Environment',"
        " module_environment: '_Rule44Environment',"
        " enclosing_functions: 'tuple[_Rule44Scope, ...]',"
        " scope_environment: '_Rule44Environment', module_name: 'str', rel: 'str',"
        " violations: 'list[str]', deferred: '_Rule44DeferredBodies | None' = None,"
        " intermediates: '_Rule44Environment | None' = None,"
        " skip_first_intermediate: 'bool' = False) -> 'None'"
    ),
    "_rule_44_scan_expression": (
        "(node: 'ast.expr', environment: '_Rule44Environment', module_name: 'str',"
        " rel: 'str', violations: 'list[str]',"
        " walrus_environment: '_Rule44Environment | None' = None,"
        " conditional: 'bool' = False, short_circuited: 'bool' = False) -> 'None'"
    ),
    "_rule_44_scan_function": (
        "(function: 'ast.FunctionDef | ast.AsyncFunctionDef',"
        " defining_environment: '_Rule44Environment',"
        " module_environment: '_Rule44Environment',"
        " enclosing_functions: 'tuple[_Rule44Scope, ...]', module_name: 'str', rel: 'str',"
        " violations: 'list[str]') -> 'None'"
    ),
    "_rule_44_scan_statement": (
        "(statement: 'ast.stmt', environment: '_Rule44Environment',"
        " module_environment: '_Rule44Environment',"
        " enclosing_functions: 'tuple[_Rule44Scope, ...]',"
        " scope_environment: '_Rule44Environment', module_name: 'str', rel: 'str',"
        " violations: 'list[str]', deferred: '_Rule44DeferredBodies',"
        " intermediates: '_Rule44Environment | None') -> 'None'"
    ),
    "_rule_44_scope_declarations": ("(body: 'list[ast.stmt]') -> 'tuple[set[str], set[str]]'"),
    "rule_44_role_checks": "(corpus: 'Corpus') -> 'list[str]'",
}

#: Each pre-split name's private sibling home; the facade re-exports the very
#: object its home defines.
FROZEN_HOMES = {
    "_rule44_names": (
        "RULE_44_MEMBERSHIP_APP",
        "RULE_44_MEMBERSHIP_MODEL",
        "RULE_44_MEMBERSHIP_SOURCE",
        "RULE_44_QUERY_METHODS",
        "_RULE_44_ALIAS_PATHS",
        "_RULE_44_SOURCE_PARTS",
        "_Rule44DeferredBodies",
        "_Rule44Environment",
        "_Rule44Scope",
        "_rule_44_argument_names",
        "_rule_44_block_bindings",
        "_rule_44_bound_names",
        "_rule_44_definition_expressions",
        "_rule_44_expression_bindings",
        "_rule_44_membership_receiver",
        "_rule_44_names_membership_model",
        "_rule_44_pattern_names",
        "_rule_44_qualified_membership",
        "_rule_44_scope_declarations",
    ),
    "_rule44_expressions": (
        "_rule_44_bind",
        "_rule_44_call_violation",
        "_rule_44_scan_expression",
    ),
    "_rule44_statements": (
        "_rule_44_scan_block",
        "_rule_44_scan_function",
        "_rule_44_scan_statement",
    ),
}

#: The corpora sources, one ``services.py`` per case; each is the same shape
#: the rule-44 control suite exercises.
CASE_SOURCES = {
    "billing_style": (
        '"""Demo service surface."""\n\n'
        "from django.apps import apps\n\n\n"
        "def recheck(user, organization):\n"
        "    membership_model = apps.get_model(\n"
        '        "quickscale_orgs",\n'
        '        "OrganizationMembership",\n'
        "    )\n"
        "    return membership_model._default_manager.filter(\n"
        "        user=user,\n"
        "        organization=organization,\n"
        '        role="owner",\n'
        "    ).exists()\n"
    ),
    "direct": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners():\n"
        "    return OrganizationMembership.objects.filter(role='owner')\n"
    ),
    "chained": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(user):\n"
        "    return (\n"
        "        OrganizationMembership.objects\n"
        "        .select_for_update()\n"
        "        .filter(user=user)\n"
        '        .filter(role="owner")\n'
        "    )\n"
    ),
    "dotted_lookup": (
        '"""Demo service surface."""\n\n'
        "from django.apps import apps\n\n\n"
        "def owners(user):\n"
        '    membership_model = apps.get_model("quickscale_orgs.OrganizationMembership")\n'
        "    return membership_model.objects.filter(user=user, role='owner')\n"
    ),
    "queryset_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(user):\n"
        "    memberships = OrganizationMembership.objects.filter(user=user)\n"
        "    return memberships.filter(role='owner')\n"
    ),
    "async_query": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "async def owners(user, organization):\n"
        "    return await OrganizationMembership.objects.aget(\n"
        "        user=user, organization=organization, role='owner'\n"
        "    )\n"
    ),
    "default_argument": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(qs=OrganizationMembership.objects.filter(role='owner')):\n"
        "    return qs\n"
    ),
    "class_rebinding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
        "qs = OrganizationMembership.objects.all()\n\n\n"
        "class Owners:\n"
        "    qs = qs.filter(role='owner')\n"
    ),
    "global_rebinding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
        "qs = OrganizationMembership.objects.all()\n\n\n"
        "def owners(user):\n"
        "    global qs\n"
        "    qs = qs.filter(user=user)\n"
        "    return qs.filter(role='owner')\n"
    ),
    "nested_global": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n"
        "qs = OrganizationMembership.objects.all()\n\n\n"
        "def outer():\n"
        "    qs = Contact.objects.all()\n\n"
        "    def owners():\n"
        "        global qs\n"
        "        return qs.filter(role='owner')\n\n"
        "    return owners\n"
    ),
    "branch_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(cond):\n"
        "    if cond:\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "    return qs.filter(role='owner')\n"
    ),
    "try_else": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners():\n"
        "    try:\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "    except Exception:\n"
        "        return None\n"
        "    else:\n"
        "        return qs.filter(role='owner')\n"
    ),
    "with_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners():\n"
        "    with transaction.atomic():\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "    return qs.filter(role='owner')\n"
    ),
    "late_module_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners():\n"
        "    return qs.filter(role='owner')\n\n\n"
        "qs = OrganizationMembership.objects.all()\n"
    ),
    "sibling_scopes": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def memberships(user):\n"
        "    qs = OrganizationMembership.objects.filter(user=user)\n"
        "    return qs.filter(role='owner')\n\n\n"
        "def contacts(user):\n"
        "    qs = Contact.objects.filter(user=user)\n"
        "    return qs.filter(role='owner')\n"
    ),
    "nonlocal_provenance": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def outer():\n"
        "    def middle():\n"
        "        qs = OrganizationMembership.objects.all()\n\n"
        "        def owners():\n"
        "            nonlocal qs\n"
        "            return qs.filter(role='owner')\n\n"
        "        return owners\n\n"
        "    return middle\n"
    ),
    "finally_intermediate": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def owners():\n"
        "    qs = Contact.objects.all()\n"
        "    try:\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "        work()\n"
        "        qs = Contact.objects.all()\n"
        "    except ValueError:\n"
        "        pass\n"
        "    finally:\n"
        "        return qs.filter(role='owner')\n"
    ),
    "finally_exception": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def owners():\n"
        "    qs = Contact.objects.all()\n"
        "    try:\n"
        "        try:\n"
        "            pass\n"
        "        finally:\n"
        "            qs = OrganizationMembership.objects.all()\n"
        "            work()\n"
        "            qs = Contact.objects.all()\n"
        "    finally:\n"
        "        return qs.filter(role='owner')\n"
    ),
    "deferred_other_branch": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def owners(flag):\n"
        "    qs = Contact.objects.all()\n"
        "    if flag:\n"
        "        def check():\n"
        "            return qs.filter(role='owner')\n"
        "    else:\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "    return check\n"
    ),
    "alias_joined": (
        '"""Demo service surface."""\n\n'
        "def owners(flag):\n"
        "    if flag:\n"
        "        import quickscale_modules_orgs.models as orgs\n"
        "    else:\n"
        "        import quickscale_modules_orgs as orgs\n"
        "    return orgs.OrganizationMembership.objects.filter(role='owner')\n"
    ),
    "comprehension_zero_iteration": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def owners(users):\n"
        "    qs = OrganizationMembership.objects.all()\n"
        "    [qs := Contact.objects.get(pk=user.pk) for user in users]\n"
        "    return qs.filter(role='owner')\n"
    ),
    "comprehension_short_circuit": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def owners(users, flag):\n"
        "    qs = OrganizationMembership.objects.all()\n"
        "    return [\n"
        "        qs.filter(role='owner')\n"
        "        for user in users\n"
        "        if flag or (qs := Contact.objects.all())\n"
        "    ]\n"
    ),
    "match_guard_rebinding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(payload):\n"
        "    qs = OrganizationMembership.objects.all()\n"
        "    match payload:\n"
        "        case {'queryset': qs}:\n"
        "            pass\n"
        "        case _ if (qs := OrganizationMembership.objects.all()).exists():\n"
        "            pass\n"
        "    return qs.filter(role='owner')\n"
    ),
    "for_loop_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(users):\n"
        "    for user in users:\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "    return qs.filter(role='owner')\n"
    ),
    "for_loop_header_shadow": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
        "qs = OrganizationMembership.objects.all()\n\n\n"
        "def contacts(items):\n"
        "    for qs in items:\n"
        "        pass\n"
        "    return qs.filter(role='owner')\n"
    ),
    "while_loop_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(flag):\n"
        "    while flag:\n"
        "        qs = OrganizationMembership.objects.all()\n"
        "        flag = False\n"
        "    return qs.filter(role='owner')\n"
    ),
    "if_exp_branch": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n"
        "from another_app.models import Contact\n\n\n"
        "def owners(flag):\n"
        "    return (\n"
        "        OrganizationMembership.objects.filter(role='owner')\n"
        "        if flag\n"
        "        else Contact.objects.all()\n"
        "    )\n"
    ),
    "dict_comprehension_binding": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(users):\n"
        "    rows = {user: (qs := OrganizationMembership.objects.all()) for user in users}\n"
        "    return qs.filter(role='owner')\n"
    ),
    "delete_shadow": (
        '"""Demo service surface."""\n\n'
        "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
        "def owners(payload):\n"
        "    qs = OrganizationMembership.objects.all()\n"
        "    del payload, qs\n"
        "    return qs.filter(role='owner')\n"
    ),
}

CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    **{
        name: (lambda source=source: _corpus(_with_files(_golden_module(), services=source)))
        for name, source in CASE_SOURCES.items()
    },
    "two_modules_order": lambda: _corpus(
        _with_files(_golden_module("demo"), services=CASE_SOURCES["direct"]),
        _with_files(_golden_module("blog"), services=CASE_SOURCES["billing_style"]),
    ),
    "orgs_skip": lambda: _corpus(
        _with_files(_golden_module("orgs"), services=CASE_SOURCES["direct"])
    ),
}

#: (case, expected findings) captured from the pre-split module; each list is
#: exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", ()),
    (
        "billing_style",
        (
            "rule 44: demo: services.py:11 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "direct",
        (
            "rule 44: demo: services.py:7 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "chained",
        (
            "rule 44: demo: services.py:8 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "dotted_lookup",
        (
            "rule 44: demo: services.py:8 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "queryset_binding",
        (
            "rule 44: demo: services.py:8 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "async_query",
        (
            "rule 44: demo: services.py:7 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "default_argument",
        (
            "rule 44: demo: services.py:6 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "class_rebinding",
        (
            "rule 44: demo: services.py:9 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "global_rebinding",
        (
            "rule 44: demo: services.py:11 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "nested_global",
        (
            "rule 44: demo: services.py:14 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "branch_binding",
        (
            "rule 44: demo: services.py:9 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "try_else",
        (
            "rule 44: demo: services.py:12 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "with_binding",
        (
            "rule 44: demo: services.py:9 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "late_module_binding",
        (
            "rule 44: demo: services.py:7 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "sibling_scopes",
        (
            "rule 44: demo: services.py:9 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "nonlocal_provenance",
        (
            "rule 44: demo: services.py:12 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "finally_intermediate",
        (
            "rule 44: demo: services.py:16 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "finally_exception",
        (
            "rule 44: demo: services.py:17 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "deferred_other_branch",
        (
            "rule 44: demo: services.py:11 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "alias_joined",
        (
            "rule 44: demo: services.py:8 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "comprehension_zero_iteration",
        (
            "rule 44: demo: services.py:10 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "comprehension_short_circuit",
        (
            "rule 44: demo: services.py:10 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "match_guard_rebinding",
        (
            "rule 44: demo: services.py:13 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "for_loop_binding",
        (
            "rule 44: demo: services.py:9 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "for_loop_header_shadow",
        (
            "rule 44: demo: services.py:11 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "while_loop_binding",
        (
            "rule 44: demo: services.py:10 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "if_exp_branch",
        (
            "rule 44: demo: services.py:9 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    (
        "dict_comprehension_binding",
        (
            "rule 44: demo: services.py:8 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    ("delete_shadow", ()),
    (
        "two_modules_order",
        (
            "rule 44: demo: services.py:7 filters OrganizationMembership by string role "
            "'owner' outside orgs",
            "rule 44: blog: services.py:11 filters OrganizationMembership by string role "
            "'owner' outside orgs",
        ),
    ),
    ("orgs_skip", ()),
)


def test_facade_publishes_the_pre_split_surface() -> None:
    """The facade's ``__all__`` is the pre-split module's own name set."""
    assert rule_44.__all__ == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert getattr(rule_44, name) is not None


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert rule_44.ast is ast
    assert rule_44.Mapping is not None
    for name in FROZEN_IMPORTED_BINDINGS:
        assert getattr(rule_44, name) is not None
    for name in FROZEN_CORE_HELPERS:
        assert getattr(rule_44, name) is getattr(core, name)


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    assert {
        name: str(inspect.signature(getattr(rule_44, name))) for name in FROZEN_SIGNATURES
    } == FROZEN_SIGNATURES


def test_frozen_type_aliases_are_unchanged() -> None:
    """The two pre-split type aliases keep their pre-split structure."""
    scope = rule_44._Rule44Scope
    assert scope.__origin__ is tuple
    assert scope.__args__ == ("_Rule44Environment", frozenset[str])
    deferred = rule_44._Rule44DeferredBodies
    assert deferred.__origin__ is list
    (body,) = deferred.__args__
    assert body.__origin__ is tuple
    assert body.__args__[0] == ast.FunctionDef | ast.AsyncFunctionDef
    assert body.__args__[1] == "_Rule44Environment"
    assert body.__args__[2] == tuple[scope, ...]


def test_rule_37_keeps_only_the_facade_exempt() -> None:
    """The split keeps the tables in the exempt facade; siblings stay closed."""
    assert (
        "scripts",
        "module_conventions/rule_44.py",
    ) in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in RULE_37_ALLOWED_LITERAL_FILES


def test_rule_37_finds_no_sibling_literal_without_exemptions() -> None:
    """The siblings carry no module-name table, so no exemption is needed."""
    corpus = core.load_corpus(REPO_ROOT)
    vocabulary = {module.name for module in corpus.modules}
    for name, module in SPLIT_SIBLINGS.items():
        findings = _module_list_violations(
            "scripts",
            f"module_conventions/{name}.py",
            Path(module.__file__).read_text(encoding="utf-8"),
            vocabulary,
            frozenset(),
            {},
            {},
            {},
        )
        assert findings == [], findings


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rule_44", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rule_44", "registry"}, (
                        name,
                        node.lineno,
                    )


def test_orchestrators_and_helpers_keep_their_homes() -> None:
    """Rule 44 stays orchestrated by the facade; the mechanics move out."""
    assert rule_44.rule_44_role_checks.__module__ == "scripts.module_conventions.rule_44"
    for sibling, names in FROZEN_HOMES.items():
        for name in names:
            assert getattr(rule_44, name) is getattr(SPLIT_SIBLINGS[sibling], name), name
    for name in (
        "_rule_44_scan_comprehension",
        "_rule_44_scan_lambda",
        "_rule_44_scan_bool_op",
        "_rule_44_scan_if_expression",
        "_rule_44_scan_walrus",
        "_rule_44_scan_expression_children",
    ):
        assert getattr(_rule44_expressions, name).__module__ == (
            "scripts.module_conventions._rule44_expressions"
        ), name
    for name in (
        "_rule_44_scan_definition",
        "_rule_44_scan_assignment",
        "_rule_44_scan_import",
        "_rule_44_scan_loop",
        "_rule_44_scan_with",
        "_rule_44_scan_conditional",
        "_rule_44_scan_try",
        "_rule_44_scan_match",
    ):
        assert getattr(_rule44_statements, name).__module__ == (
            "scripts.module_conventions._rule44_statements"
        ), name


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registry's detector is the facade callable, not a sibling."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    assert detectors[44] is rule_44.rule_44_role_checks
    assert checker.rule_44_role_checks is rule_44.rule_44_role_checks


@pytest.mark.parametrize(
    ("case", "expected"),
    EXACT_FINDINGS,
    ids=[case for case, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(case: str, expected: tuple[str, ...]) -> None:
    assert rule_44.rule_44_role_checks(CASE_BUILDERS[case]()) == list(expected)
