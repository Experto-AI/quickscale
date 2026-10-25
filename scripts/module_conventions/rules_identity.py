"""
Identity and naming rules: names, stems, references, file and test names.

The mechanics live in private sibling modules grouped by rule theme
(``_identity_names``, ``_identity_conventions``, ``_identity_tests``,
``_identity_stems``, ``_identity_references``, ``_identity_files``,
``_identity_module_lists``); this module keeps rule 37's and rule 28's
module-name exception tables (rule 37's allowlist exempts only
``rules_identity.py``), orchestrates rule 37's per-file scan, and re-exports
every moved name so existing import paths and the rule registry keep working.
"""

from __future__ import annotations

from scripts.module_conventions._identity_conventions import (
    AMBIGUOUS_BINDING,
    _add_import_bindings,
    _collect_scope_imports,
    _datetime_now_calls,
    _resolve_module_path,
    _resolves_to_stdlib_datetime,
    _visit_definition_expressions,
    rule_24_small_conventions,
)
from scripts.module_conventions._identity_files import (
    _facade_targets,
    _module_named_logger_line,
)
from scripts.module_conventions._identity_module_lists import (
    _TEMPLATE_BRACKET_LITERAL,
    _TEMPLATE_PIPE_GROUP,
    _TEMPLATE_QUOTED_NAME,
    RULE_37_BRANCH_OPERANDS,
    RULE_37_BRANCH_OPERATORS,
    RULE_37_MINIMUM_MODULE_NAMES,
    _module_list_violations,
    _module_literal_names,
    _module_name_branches,
    _module_prefixed_constants,
    _string_module_alternations,
    _template_module_literals,
)
from scripts.module_conventions._identity_names import rule_2_identity_names
from scripts.module_conventions._identity_references import (
    _is_migration_model_path,
    _migration_model_reference_ids,
    _name_reference_target,
    rule_34_name_references,
)
from scripts.module_conventions._identity_stems import (
    _is_session_receiver,
    _session_literal_keys,
    rule_33_shared_stems,
)
from scripts.module_conventions._identity_tests import (
    TICKET_IN_SHIPPED,
    TICKET_IN_TEST,
    _tests_entry_allowed,
    rule_29_test_names,
)
from scripts.module_conventions.core import (
    ORG_PUBLIC_SURFACE,
    Corpus,
    _parse,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through
#: this facade.
__all__ = (
    "AMBIGUOUS_BINDING",
    "RULE_28_ALLOWED_DIRS",
    "RULE_28_ALLOWED_FILES",
    "RULE_28_ALLOWED_NON_PYTHON",
    "RULE_28_LISTED_EXTRA_FILES",
    "RULE_37_ALLOWED_BRANCHES",
    "RULE_37_ALLOWED_CONSTANTS",
    "RULE_37_ALLOWED_LITERALS",
    "RULE_37_ALLOWED_LITERAL_FILES",
    "RULE_37_BRANCH_OPERANDS",
    "RULE_37_BRANCH_OPERATORS",
    "RULE_37_MINIMUM_MODULE_NAMES",
    "TICKET_IN_SHIPPED",
    "TICKET_IN_TEST",
    "_TEMPLATE_BRACKET_LITERAL",
    "_TEMPLATE_PIPE_GROUP",
    "_TEMPLATE_QUOTED_NAME",
    "_add_import_bindings",
    "_collect_scope_imports",
    "_datetime_now_calls",
    "_facade_targets",
    "_is_migration_model_path",
    "_is_session_receiver",
    "_migration_model_reference_ids",
    "_module_literal_names",
    "_module_name_branches",
    "_module_named_logger_line",
    "_module_prefixed_constants",
    "_name_reference_target",
    "_resolve_module_path",
    "_resolves_to_stdlib_datetime",
    "_session_literal_keys",
    "_string_module_alternations",
    "_template_module_literals",
    "_tests_entry_allowed",
    "_visit_definition_expressions",
    "rule_24_small_conventions",
    "rule_28_file_names",
    "rule_29_test_names",
    "rule_2_identity_names",
    "rule_33_shared_stems",
    "rule_34_name_references",
    "rule_37_module_lists",
)
# Rule 28's allowed package-file names: rule 11's files, rule 10's files,
# rule 16's files, the Django and DRF names, and auth's allauth adapter.
RULE_28_ALLOWED_FILES = frozenset(
    {
        "__init__.py",
        "admin.py",
        "adapter.py",
        "allauth_adapter.py",
        "apps.py",
        "checks.py",
        "exceptions.py",
        "feeds.py",
        "filters.py",
        "forms.py",
        "managers.py",
        "middleware.py",
        "models.py",
        "permissions.py",
        "receivers.py",
        "serializers.py",
        "services.py",
        "signals.py",
        "throttles.py",
        "urls.py",
        "validators.py",
        "views.py",
    }
)

RULE_28_ALLOWED_DIRS = frozenset(
    {"templatetags", "management", "migrations", "templates", "static"}
)

# Rule 28's listed extras: the public-looking names decision §28 names.
RULE_28_LISTED_EXTRA_FILES: dict[str, frozenset[str]] = {
    "backups": frozenset({"persistence.py"}),
    "orgs": frozenset({"debug_views.py"}),
    "billing": frozenset({"webhook_urls.py"}),
    "storage": frozenset({"markdownx_urls.py"}),
}

RULE_28_ALLOWED_NON_PYTHON = frozenset({"py.typed"})

# Rule 37's allowed literal collections: core's declared release inventory and
# two recorded presentation catalogs (the `.env.example` managed-block specs,
# whose per-module prose and block order are presentation data pinned by the
# env-example conformance suite, and the theme seam's server-resolved path
# table), plus the rule-40 harness package itself, which is the test-owned
# mapping the rule names as an exception.  The theme's TypeScript module
# surfaces are rule 31's, outside this corpus.
RULE_37_ALLOWED_LITERAL_FILES: frozenset[tuple[str, str]] = frozenset(
    {
        ("scripts", "check_module_conventions.py"),
        ("scripts", "module_conventions/core.py"),
        ("scripts", "module_conventions/registry.py"),
        ("scripts", "module_conventions/rule_44.py"),
        ("scripts", "module_conventions/rules_analytics.py"),
        ("scripts", "module_conventions/rules_dependencies.py"),
        ("scripts", "module_conventions/rules_docs.py"),
        ("scripts", "module_conventions/rules_identity.py"),
        ("scripts", "module_conventions/rules_misc.py"),
        ("scripts", "module_conventions/rules_models.py"),
        ("scripts", "module_conventions/rules_package.py"),
        ("scripts", "module_conventions/rules_routes.py"),
        ("scripts", "module_conventions/rules_settings.py"),
        ("scripts", "module_conventions/rules_webhooks.py"),
    }
)

RULE_37_ALLOWED_LITERALS: dict[tuple[str, str, str], str] = {
    ("core", "contracts/module_catalog.py", "MODULE_CATALOG"): (
        "rule 37's declared release inventory"
    ),
    ("core", "apply/steps/env_sync.py", "ENV_EXAMPLE_MODULE_SPECS"): (
        "the .env.example managed-block presentation catalog"
    ),
    ("core", "runtime/seam.py", "_SEAM_MODULE_PATHS"): (
        "the theme seam's server-resolved path table (rule 31)"
    ),
    ("core", "runtime/seam.py", "_SEAM_MODULE_API_PATHS"): (
        "the theme seam's server-resolved API-base table (rule 41)"
    ),
    ("core", "runtime/seam.py", "_SEAM_DOCUMENT_PATHS"): (
        "the theme seam's server-resolved document-path table (rule 31)"
    ),
    ("core", "runtime/seam.py", "_NON_SEAM_MODULES"): (
        "the theme's documented orgs exclusion (rule 31)"
    ),
    ("cli", "utils/auth_migration.py", "_CORE_AUTH_APPS"): (
        "Django contrib app labels, not QuickScale module names"
    ),
    ("scripts", "check_module_core_compatibility.py", "SKIP_INSTALL_PROBE_MODULES"): (
        "the documented install/import probe exclusion"
    ),
    ("scripts", "check_org_context_primitives.py", "EXEMPT_MODULES"): (
        "the documented orgs lint exemption"
    ),
    ("core", "runtime/urls.py", "_TEMPLATE_MODULE_URLS"): (
        "the theme's server-side template URL table (rule 41), the sibling of "
        "runtime/seam._SEAM_MODULE_PATHS"
    ),
    (
        "core",
        "runtime/urls.py",
        "<string alternation:blog|listings|members|settings>",
    ): "the theme's host URLconf route table (rule 41)",
}  #: Two or more distinct module names in one literal is a module enumeration

#: Rule 37's recorded exceptions, each with the reason the rule accepts it.
#: A branch names a discovered module in a comparison, a ``.get()`` call, or a
#: subscript; a constant is declared with a module-name prefix.  Keys are
#: (tree, relative path, module name or constant name).
RULE_37_ALLOWED_BRANCHES: dict[tuple[str, str, str], str] = {
    ("cli", "utils/_dependency_io.py", "storage"): (
        "storage's cloud extra selects the module's optional boto3/django-storages "
        "dependencies from its backend option; the manifest dependency model "
        "carries names only, so the condition has no generic home yet"
    ),
    ("cli", "commands/_module_embed.py", "auth"): (
        "auth's split-branch migration gate runs before the embedded module is "
        "importable, so it cannot live in the module's adapter"
    ),
    **{
        ("cli", "commands/_finalize.py", name): (
            "operator next-steps text: the apply summary's per-module setup "
            "guidance is presentation data the module manifests do not declare"
        )
        for name in ("analytics", "backups", "billing", "notifications", "social")
    },
    ("cli", "commands/_runtime.py", "backups"): (
        "backups' artifact-directory .gitignore adoption: an apply-side effect "
        "of the module's local_directory option that the manifest does not declare"
    ),
    ("core", "dr_engine/_media.py", "storage"): (
        "the media-runtime descriptor's own `storage` field carries the resolved "
        "storage handle; the key is not the storage module name"
    ),
}

RULE_37_ALLOWED_CONSTANTS: dict[tuple[str, str, str], str] = {
    ("cli", "utils/_dependency_io.py", "_STORAGE_CLOUD_BACKENDS"): (
        "storage's cloud-extra projection (see the branch exception above)"
    ),
    ("cli", "utils/_dependency_io.py", "_STORAGE_CLOUD_DEPENDENCIES"): (
        "storage's cloud-extra projection (see the branch exception above)"
    ),
    ("cli", "utils/_dependency_io.py", "_STORAGE_CLOUD_EXTRA"): (
        "storage's cloud-extra projection (see the branch exception above)"
    ),
    **{
        ("core", "contracts/module_options.py", name): (
            "core's exported option-name and environment constants that its generic "
            "env-sync and secret-projection plumbing and the CLI's operator output read"
        )
        for name in (
            "ANALYTICS_PROVIDER_POSTHOG",
            "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
            "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
            "BILLING_ENV_VAR_OPTION_NAMES",
            "NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION",
            "NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION",
            "SOCIAL_EMBEDS_PATH",
            "SOCIAL_INTEGRATION_BASE_PATH",
            "SOCIAL_INTEGRATION_EMBEDS_PATH",
            "SOCIAL_LINK_TREE_PATH",
            "STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION",
            "STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
        )
    },
    **{
        ("core", "manifest/social_manifest.py", name): (
            "social's runtime and generated payload views are hosted in core pending "
            "the arch watchlist `core-holds-module-vocabulary`"
        )
        for name in (
            "_SOCIAL_PROVIDER_ALIASES",
            "_SOCIAL_PROVIDER_BY_HOST",
            "_SOCIAL_PROVIDER_BY_NAME",
            "SOCIAL_LAYOUT_VARIANTS",
            "SOCIAL_PAYLOAD_HTTP_STATUS",
            "SOCIAL_PAYLOAD_STATUSES",
            "SOCIAL_PROVIDER_CATALOG",
            "SOCIAL_STATUS_DISABLED",
            "SOCIAL_STATUS_EMPTY",
            "SOCIAL_STATUS_ENABLED",
            "SOCIAL_STATUS_ERROR",
        )
    },
}


def rule_28_file_names(corpus: Corpus) -> list[str]:
    """
    Rule 28: a package holds only its allowed public and private files.

    A private file that has a facade (a public sibling imports it) also logs on
    the facade's channel: ``getLogger(__name__)`` there is rule 46's violation.
    """
    violations: list[str] = []
    orgs_surface = {f"{stem}.py" for stem in ORG_PUBLIC_SURFACE}
    for module in corpus.modules:
        allowed_extras = RULE_28_LISTED_EXTRA_FILES.get(module.name, frozenset())
        for entry in sorted({rel.split("/", 1)[0] for rel in module.files}):
            if entry in RULE_28_ALLOWED_DIRS or entry in RULE_28_ALLOWED_FILES:
                continue
            if entry in RULE_28_ALLOWED_NON_PYTHON:
                continue
            if entry.startswith("_") and entry.endswith(".py"):
                continue
            if module.name == "orgs" and entry in orgs_surface:
                continue
            if entry in allowed_extras:
                continue
            violations.append(
                f"rule 28: {module.name}: {entry} is not an allowed package file name"
            )
        for private_name in sorted(_facade_targets(module)):
            source = module.files.get(f"{private_name}.py")
            if source is None:
                continue
            logger_line = _module_named_logger_line(_parse(source))
            if logger_line is not None:
                violations.append(
                    f"rule 28: {module.name}: {private_name}.py:{logger_line} calls "
                    "getLogger(__name__); a private file with a facade logs on the "
                    "facade's channel (rule 46)"
                )
    return violations


def rule_37_module_lists(corpus: Corpus) -> list[str]:
    """Rule 37: no literal module-name list outside the modules."""
    vocabulary = {module.name for module in corpus.modules}
    violations: list[str] = []
    for tree_name, files in (
        ("core", corpus.core_files),
        ("cli", corpus.cli_files),
        ("scripts", corpus.script_files),
    ):
        for rel, text in files.items():
            violations.extend(
                _module_list_violations(
                    tree_name,
                    rel,
                    text,
                    vocabulary,
                    RULE_37_ALLOWED_LITERAL_FILES,
                    RULE_37_ALLOWED_LITERALS,
                    RULE_37_ALLOWED_BRANCHES,
                    RULE_37_ALLOWED_CONSTANTS,
                )
            )
    return violations
