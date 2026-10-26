"""
Route, template, API, authorization, theme-seam, and throttle rules.

The mechanics live in private sibling modules grouped by rule theme
(``_routes_urls``, ``_routes_templates``, ``_routes_http_apis``,
``_routes_view_index``, ``_routes_authorization``, ``_routes_theme_seam``,
``_routes_throttles``); this module keeps rule 37's module-name exception
tables (rule 37's allowlist exempts only ``rules_routes.py``), orchestrates
rule 7's and rule 19's ordered finding groups, and re-exports every moved name
so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import re

from scripts.module_conventions._routes_authorization import (
    FORBIDDEN_VIEW_TOKENS,
    GUARD_MIXIN_NAMES,
    PUBLIC_READ_MIXIN_NAMES,
    PUBLIC_READ_MIXIN_SUFFIX,
    ROLE_ENFORCING_BASE_NAMES,
    _allow_any_hand_check_violations,
    _class_declares_guard,
    _declares_min_org_role,
    _declares_permission_classes,
    _effective_methods,
    _effective_permission_names,
    _get_permissions_binding,
    _guard_violations,
    _inherits_role_enforcement,
    _is_sanctioned_guard_name,
    _module_helper_index,
    _permission_expression_name,
    _reads_user_is_authenticated,
    _sibling_rel,
    _token_violations,
    _view_token,
)
from scripts.module_conventions._routes_http_apis import (
    CORE_LIST_PAGINATION,
    CORE_SESSION_AUTHENTICATION,
    _declares_page_size_setting,
    _pagination_bindings,
    _pagination_violations,
    _paginator_classifications,
    _rendered_managed_json_violations,
    _resolves_to_core_list_pagination,
    _resolves_to_core_session_authentication,
    _resolves_to_drf_page_number_pagination,
    _resolves_to_drf_session_authentication,
    _session_authentication_bindings,
    _session_authentication_violations,
    _sibling_paginator_imports,
)
from scripts.module_conventions._routes_http_apis import (
    rule_9_http_apis as _rule_9_http_apis,
)
from scripts.module_conventions._routes_templates import (
    _is_admin_model_override,
    rule_8_templates,
)
from scripts.module_conventions._routes_theme_seam import (
    SEAM_LIBRARY_LOAD,
    THEME_SEAM_TEMPLATE,
    THEME_SEAM_TEMPLATES,
    rule_31_theme_seam,
)
from scripts.module_conventions._routes_throttles import (
    RATE_LITERAL,
    _throttle_registration_violations,
    _webhook_view_names,
    rule_32_throttles,
)
from scripts.module_conventions._routes_urls import (
    THEME_TS_ROOT,
    THEME_TS_TEST_MARKER,
    WIRING_LITERAL_FIELDS,
    _adapter_literal_wiring_violations,
    _declares_literal_wiring,
    _module_url_violations,
    _route_name_violations,
    _theme_api_literal_violations,
    _url_prefix_collision_violations,
)
from scripts.module_conventions._routes_view_index import (
    DJANGO_VIEW_MODULE_PREFIXES,
    DRF_VIEW_MODULE_PREFIXES,
    VIEW_MODULE_PREFIXES,
    _base_name,
    _base_view_target,
    _defines_view_class,
    _defines_view_code,
    _dotted_name,
    _is_view_base,
    _is_view_module,
    _takes_request,
    _view_bindings,
    _view_class_index,
    _view_framework,
)
from scripts.module_conventions.core import (
    GENERATOR_TEMPLATE_ROOT,
    Corpus,
    _declared_mounts,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) and test patch targets keep
#: resolving through this facade.
__all__ = (
    "CORE_LIST_PAGINATION",
    "CORE_SESSION_AUTHENTICATION",
    "DJANGO_VIEW_MODULE_PREFIXES",
    "DRF_VIEW_MODULE_PREFIXES",
    "FORBIDDEN_VIEW_TOKENS",
    "GUARD_MIXIN_NAMES",
    "OPERATOR_TOKENS",
    "PUBLIC_READ_MIXIN_NAMES",
    "PUBLIC_READ_MIXIN_SUFFIX",
    "RATE_LITERAL",
    "ROLE_ENFORCING_BASE_NAMES",
    "RULE_7_ALLOWED_TEMPLATE_MOUNTS",
    "SEAM_LIBRARY_LOAD",
    "THEME_SEAM_TEMPLATE",
    "THEME_SEAM_TEMPLATES",
    "THEME_TS_ROOT",
    "THEME_TS_TEST_MARKER",
    "TRAFFIC_FILTER_TOKENS",
    "VIEW_MODULE_PREFIXES",
    "WIRING_LITERAL_FIELDS",
    "_adapter_literal_wiring_violations",
    "_allow_any_hand_check_violations",
    "_base_name",
    "_base_view_target",
    "_class_declares_guard",
    "_declares_literal_wiring",
    "_declares_min_org_role",
    "_declares_page_size_setting",
    "_declares_permission_classes",
    "_defines_view_class",
    "_defines_view_code",
    "_dotted_name",
    "_effective_methods",
    "_effective_permission_names",
    "_get_permissions_binding",
    "_inherits_role_enforcement",
    "_is_admin_model_override",
    "_is_sanctioned_guard_name",
    "_is_view_base",
    "_is_view_module",
    "_module_helper_index",
    "_pagination_bindings",
    "_pagination_violations",
    "_paginator_classifications",
    "_permission_expression_name",
    "_reads_user_is_authenticated",
    "_rendered_managed_json_violations",
    "_resolves_to_core_list_pagination",
    "_resolves_to_core_session_authentication",
    "_resolves_to_drf_page_number_pagination",
    "_resolves_to_drf_session_authentication",
    "_route_name_violations",
    "_session_authentication_bindings",
    "_session_authentication_violations",
    "_sibling_paginator_imports",
    "_sibling_rel",
    "_takes_request",
    "_template_mount_literal_violations",
    "_theme_api_literal_violations",
    "_throttle_registration_violations",
    "_url_prefix_collision_violations",
    "_view_bindings",
    "_view_class_index",
    "_view_framework",
    "_view_token",
    "_webhook_view_names",
    "rule_19_authorization",
    "rule_31_theme_seam",
    "rule_32_throttles",
    "rule_7_urls",
    "rule_8_templates",
    "rule_9_http_apis",
)

#: Rule 9's published-gate contract: a gate decorator answers an error by
#: raising a declared module error (rule 10) so the one exception handler
#: renders the shared shape; a bare response would reach a JSON client as an
#: empty body.  A gate that only wraps an HTML view is recorded here with the
#: reason it is sanctioned.
HTML_ONLY_GATES: dict[tuple[str, str, str], str] = {
    ("orgs", "permissions.py", "require_org_role"): (
        "HTML page gate: it returns a blank forbidden response directly and no "
        "shipped JSON endpoint wraps it"
    ),
}


def rule_9_http_apis(corpus: Corpus) -> list[str]:
    """Rule 9 over the module corpus and the recorded HTML-only gates."""
    return _rule_9_http_apis(corpus, html_only_gates=HTML_ONLY_GATES)


# Rule 41's stated exceptions: orgs' tenancy-mode shell reservations and
# forms' shallow reservations stay host-rendered, but since SA258 they render
# from the versioned runtime URLconf (quickscale_core.runtime.urls) instead of
# a generator template, so no host template carries their mount.  The 404
# hints test a requested path against the module's mount; they declare no
# route.
RULE_7_ALLOWED_TEMPLATE_MOUNTS: dict[tuple[str, str], str] = {
    ("generator/templates/templates/404.html.j2", "auth"): (
        "the 404 hint tests the requested path against the module's mount; it declares no route"
    ),
    ("generator/templates/templates/404.html.j2", "billing"): (
        "the 404 hint tests the requested path against the module's mount; it declares no route"
    ),
}

# Rule 19's listed operator path where a superuser check is sanctioned
# (audited cross-tenant operator access): orgs' permissions file defines
# ``is_platform_operator``, the one helper every module calls (rule 44), so no
# other file keeps an ``is_superuser`` allowance; the listed traffic filter
# stays separate.  The tables stay defined here because rule 37's allowlist
# exempts only this module; ``_routes_authorization`` scans with them, and a
# token is sanctioned only by an explicit mapping entry.
OPERATOR_TOKENS: dict[tuple[str, str], frozenset[str]] = {
    ("orgs", "permissions.py"): frozenset({"is_superuser"}),
}

# Rule 19's listed exception for analytics' EXCLUDE_STAFF: the filter reads
# ``is_staff`` to hide analytics from staff requests, not to authorize one.
TRAFFIC_FILTER_TOKENS: dict[tuple[str, str], frozenset[str]] = {
    ("analytics", "services.py"): frozenset({"is_staff"}),
}


def rule_7_urls(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_module_url_violations(module))
    violations.extend(_template_mount_literal_violations(corpus))
    violations.extend(_url_prefix_collision_violations(corpus))
    violations.extend(_theme_api_literal_violations(corpus))
    return violations


def _template_mount_literal_violations(corpus: Corpus) -> list[str]:
    """
    Rule 7 over the generator's Jinja templates (enforcement gap 13).

    A declared module mount written as a host route literal in a ``.j2``
    file shadows the module the same way a copied mount does in Python; the
    rule-41 exceptions are the entries in ``RULE_7_ALLOWED_TEMPLATE_MOUNTS``.
    """
    violations: list[str] = []
    declared = {module.name: _declared_mounts(module) for module in corpus.modules}
    for rel, text in corpus.core_files.items():
        if not (rel.startswith(GENERATOR_TEMPLATE_ROOT) and rel.endswith(".j2")):
            continue
        for module_name, mounts in declared.items():
            if (rel, module_name) in RULE_7_ALLOWED_TEMPLATE_MOUNTS:
                continue
            for mount in mounts:
                if not mount:
                    continue
                anchor = mount.rstrip("/")
                # An anchored route claims the mount only while the mount's
                # segment ends there; ``^blogroll`` and ``^blog-roll`` are not
                # blog's mount.
                route_pattern = re.compile(rf"""[r]?["']\^{re.escape(anchor)}(?![A-Za-z0-9_-])""")
                literals = (
                    f'path("{mount}',
                    f"path('{mount}",
                    f'"/{mount}"',
                    f"'/{mount}'",
                    f'"{mount}"',
                    f"'{mount}'",
                    # A quoted absolute path under the mount (``"/billing/api/"``)
                    # repeats the mount just as the bare mount does.
                    f'"/{anchor}/',
                    f"'/{anchor}/",
                )
                if route_pattern.search(text) or any(literal in text for literal in literals):
                    violations.append(
                        f"rule 7: core {rel}: module '{module_name}' mount "
                        f"'{mount}' is written as a literal"
                    )
    return violations


def rule_19_authorization(corpus: Corpus) -> list[str]:
    """
    Rule 19: module views declare and keep their authorization guard.

    Three closed-world clauses.  First, ``is_staff``, ``is_superuser``,
    ``IsAdminUser``, and hand-written ``redirect_to_login`` — imported or
    aliased, read as an attribute, or passed as a string — appear only in the
    listed operator paths.  Second, every view class declares a guard: on a
    DRF view, a ``permission_classes`` literal (including the empty lists a
    signature-verified webhook declares) or a ``get_permissions()`` override
    that returns a literal permission list (an override the harness cannot
    classify fails closed); on any view, ``min_org_role`` beside its
    enforcing base (``OrgApiBaseView`` or ``OrgRoleMixin``),
    ``LoginRequiredMixin``/``OrgRoleMixin``, a named public-read mixin
    (``PublicSystemOrgReadMixin`` or a ``*PublicReadMixin``), or inheritance
    of one of those from a class in the same module.  DRF permission
    declarations count only where they enforce — on a DRF view or through
    its ancestry, never on a plain Django page — and permission import
    aliases resolve in the declaring class's file.  Third, an ``AllowAny``
    view must not read ``request.user.is_authenticated`` by hand, directly
    or through a helper its effective methods call; the scan follows
    inherited handlers and resolves a module-owned helper to its defining
    file, and an ``AllowAny`` a ``get_permissions`` override returns is that
    view's guard too.  Rule 46
    finds the view code to scan by content rather than by file name: every
    file that defines a Django or DRF view subclass or a function taking
    ``request``, wherever a rule 28 split files it.  The README role listing
    is rule 38's clause.
    """
    violations = _token_violations(corpus, OPERATOR_TOKENS, TRAFFIC_FILTER_TOKENS)
    for module in corpus.modules:
        violations.extend(_guard_violations(module))
    return violations
