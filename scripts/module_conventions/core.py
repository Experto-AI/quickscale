"""
Corpus loading, the authority errors, and AST helpers shared across rules.

The corpus loader, its authority errors, and the manifest readers live in the
private sibling ``_core_corpus``; the shared AST helpers live in ``_core_ast``.
This facade keeps the module-name tables rule 37 exempts here and re-exports
every moved name, so existing import paths (``registry``,
``check_module_conventions``, the rule modules, and the control cases) keep
working.  It declares no ``__all__``, exactly as the pre-split module did, so
``from ... import *`` keeps binding the same public surface.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes; the
# redundant aliases keep every one importable from this facade.
import ast as ast
import os as os
import re as re
import stat as stat
from collections.abc import Mapping as Mapping
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from typing import Any as Any
from typing import cast as cast

import yaml as yaml

# Every name the pre-split module published but no longer defines is re-exported
# here, private helpers included; the rule 40 harness keeps reading this facade.
from scripts.module_conventions._core_ast import (
    MODULE_ABSTRACT_BASES as MODULE_ABSTRACT_BASES,
)
from scripts.module_conventions._core_ast import (
    MODULE_IMPORT_PREFIX as MODULE_IMPORT_PREFIX,
)
from scripts.module_conventions._core_ast import (
    _ancestors as _ancestors,
)
from scripts.module_conventions._core_ast import (
    _attribute_chain as _attribute_chain,
)
from scripts.module_conventions._core_ast import (
    _body_nodes as _body_nodes,
)
from scripts.module_conventions._core_ast import (
    _bound_names as _bound_names,
)
from scripts.module_conventions._core_ast import (
    _call_func_name as _call_func_name,
)
from scripts.module_conventions._core_ast import (
    _class_names as _class_names,
)
from scripts.module_conventions._core_ast import (
    _cross_module_imports as _cross_module_imports,
)
from scripts.module_conventions._core_ast import (
    _declared_exports as _declared_exports,
)
from scripts.module_conventions._core_ast import (
    _declared_mounts as _declared_mounts,
)
from scripts.module_conventions._core_ast import (
    _declared_url_mounts as _declared_url_mounts,
)
from scripts.module_conventions._core_ast import (
    _docstring_nodes as _docstring_nodes,
)
from scripts.module_conventions._core_ast import (
    _import_package_parts as _import_package_parts,
)
from scripts.module_conventions._core_ast import (
    _is_settings_receiver as _is_settings_receiver,
)
from scripts.module_conventions._core_ast import (
    _keyword as _keyword,
)
from scripts.module_conventions._core_ast import (
    _literal as _literal,
)
from scripts.module_conventions._core_ast import (
    _meta_class as _meta_class,
)
from scripts.module_conventions._core_ast import (
    _model_classes as _model_classes,
)
from scripts.module_conventions._core_ast import (
    _module_target as _module_target,
)
from scripts.module_conventions._core_ast import (
    _parse as _parse,
)
from scripts.module_conventions._core_ast import (
    _projection_values as _projection_values,
)
from scripts.module_conventions._core_ast import (
    _same_layer_cycles as _same_layer_cycles,
)
from scripts.module_conventions._core_ast import (
    _scope_nodes as _scope_nodes,
)
from scripts.module_conventions._core_ast import (
    _service_module_bindings as _service_module_bindings,
)
from scripts.module_conventions._core_ast import (
    _settings_attribute_reads as _settings_attribute_reads,
)
from scripts.module_conventions._core_ast import (
    _settings_bindings as _settings_bindings,
)
from scripts.module_conventions._core_ast import (
    _static_truth as _static_truth,
)
from scripts.module_conventions._core_ast import (
    _string_assignments as _string_assignments,
)
from scripts.module_conventions._core_ast import (
    _string_list as _string_list,
)
from scripts.module_conventions._core_ast import (
    _uses_name as _uses_name,
)
from scripts.module_conventions._core_ast import (
    _wiring_projection as _wiring_projection,
)
from scripts.module_conventions._core_corpus import (
    CLI_PACKAGE as CLI_PACKAGE,
)
from scripts.module_conventions._core_corpus import (
    CORE_CONVENTIONS_RELATIVE_PATH as CORE_CONVENTIONS_RELATIVE_PATH,
)
from scripts.module_conventions._core_corpus import (
    CORE_PACKAGE as CORE_PACKAGE,
)
from scripts.module_conventions._core_corpus import (
    DECISIONS_DOC_RELATIVE_PATH as DECISIONS_DOC_RELATIVE_PATH,
)
from scripts.module_conventions._core_corpus import (
    MANIFEST_NAME as MANIFEST_NAME,
)
from scripts.module_conventions._core_corpus import (
    MODULE_REQUIRED_NAME as MODULE_REQUIRED_NAME,
)
from scripts.module_conventions._core_corpus import (
    MODULES_DIR_NAME as MODULES_DIR_NAME,
)
from scripts.module_conventions._core_corpus import (
    MYPY_INI_NAME as MYPY_INI_NAME,
)
from scripts.module_conventions._core_corpus import (
    AuthorityError as AuthorityError,
)
from scripts.module_conventions._core_corpus import (
    Corpus as Corpus,
)
from scripts.module_conventions._core_corpus import (
    Module as Module,
)
from scripts.module_conventions._core_corpus import (
    Skipped as Skipped,
)
from scripts.module_conventions._core_corpus import (
    _construct_unique_mapping as _construct_unique_mapping,
)
from scripts.module_conventions._core_corpus import (
    _credential_reference_options as _credential_reference_options,
)
from scripts.module_conventions._core_corpus import (
    _display as _display,
)
from scripts.module_conventions._core_corpus import (
    _DuplicateKeyYAMLError as _DuplicateKeyYAMLError,
)
from scripts.module_conventions._core_corpus import (
    _read_manifest as _read_manifest,
)
from scripts.module_conventions._core_corpus import (
    _read_tree as _read_tree,
)
from scripts.module_conventions._core_corpus import (
    _required_modules as _required_modules,
)
from scripts.module_conventions._core_corpus import (
    _StrictSafeLoader as _StrictSafeLoader,
)
from scripts.module_conventions._core_corpus import (
    load_corpus as load_corpus,
)

ALLOWED_TEMPLATE_DIRS = ("account", "admin")

# Rule 1's controlled vocabulary of third-party environment-variable names
# (SA263).  A credential reference option's default is the vendor's own
# variable name when the vendor names it, so an unapproved vendor-shaped
# default is a violation.  Precident collision is what the vocabulary
# prevents: a name already meaning one vendor's credential cannot become a
# second vendor's default.  An operator replacing the value at apply time is a
# supplied value, not a manifest default, so this rule never bans an override.
# This is deliberately NOT the setting-name exception table below — a setting
# exception fixes a Django/third-party setting name, an entry here fixes an
# option default.
CREDENTIAL_REFERENCE_NAMES: tuple[str, ...] = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "RESEND_API_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_SECRET_KEY",
)
# Vendor ownership is per declaration, not membership in a global vocabulary.
VENDOR_CREDENTIAL_DEFAULTS: dict[str, dict[str, str]] = {
    "analytics": {
        "posthog_api_key_env_var": "POSTHOG_API_KEY",
        "posthog_host_env_var": "POSTHOG_HOST",
    },
    "billing": {
        "publishable_key_env_var": "STRIPE_PUBLISHABLE_KEY",
        "secret_key_env_var": "STRIPE_SECRET_KEY",
    },
    "notifications": {"resend_api_key_env_var": "RESEND_API_KEY"},
    "storage": {
        "access_key_id_env_var": "AWS_ACCESS_KEY_ID",
        "secret_access_key_env_var": "AWS_SECRET_ACCESS_KEY",
    },
}
# Rule 1's per-option authorized QuickScale-defined credential names (SA263).
# A default that a module tracks in a shared namespace of its own is approved
# per option rather than by the ``QUICKSCALE_<MODULE>_`` stem alone, so a
# cross-module collision (backups' private-remote credentials sharing
# storage's media or the ambient ``AWS_*`` provider chain) stays recorded and
# reasoned.  These entries are a separate table from
# :data:`SETTING_NAME_EXCEPTIONS`: they constrain an option's *default value*,
# not its setting name.
QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS: dict[str, dict[str, dict[str, str]]] = {
    "backups": {
        "remote_access_key_id_env_var": {
            "default": "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID",
            "why": "backups' own private artifact store stays distinct from "
            "storage's media credentials and the ambient AWS_* provider chain",
        },
        "remote_secret_access_key_env_var": {
            "default": "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY",
            "why": "backups' own private artifact store stays distinct from "
            "storage's media credentials and the ambient AWS_* provider chain",
        },
    },
    "billing": {
        "webhook_secret_env_var": {
            "default": "QUICKSCALE_BILLING_WEBHOOK_SECRET",
            "why": "the webhook secret is QuickScale-defined, not a vendor name",
        },
    },
    "notifications": {
        "webhook_secret_env_var": {
            "default": "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
            "why": "the webhook secret is QuickScale-defined, not a vendor name",
        },
    },
}

# Rule 1's shape test for an environment-variable name a module declares as a
# default.  ``^[A-Z][A-Z0-9_]*$`` is the same name grammar the manifests'
# ``_ENV_VAR`` pattern uses.
ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Rule 1's listed settings-name exceptions (auth's allauth settings and
# storage's MEDIA_URL / django-storages AWS_* names) are recorded here so the
# option-schema detector checks the suffix relation, not the exception list.
SETTING_NAME_EXCEPTIONS: dict[str, dict[str, str]] = {
    "auth": {
        "registration_enabled": "ACCOUNT_ALLOW_REGISTRATION",
        "email_verification": "ACCOUNT_EMAIL_VERIFICATION",
        "session_cookie_age": "SESSION_COOKIE_AGE",
    },
    "storage": {
        "media_url": "MEDIA_URL",
        "bucket_name": "AWS_STORAGE_BUCKET_NAME",
        "endpoint_url": "AWS_S3_ENDPOINT_URL",
        "region_name": "AWS_S3_REGION_NAME",
        "default_acl": "AWS_DEFAULT_ACL",
        "querystring_auth": "AWS_QUERYSTRING_AUTH",
    },
}

# Rule 4's public surface per module: every module publishes its operations and
# questions through services.py; a foundation additionally publishes the
# extension bases other modules build on.  Orgs' list is the one decision §4
# names, and changing the list is a decision edit.
ORG_PUBLIC_SURFACE: tuple[str, ...] = (
    "services",
    "models",
    "managers",
    "admin",
    "current_org",
    "tenancy",
    "removal",
    "sanitization",
    "public_context",
    "permissions",
    "signals",
)

# Rule 5's fixed layer table; moving a module between layers is a decision edit.
MODULE_LAYERS: dict[str, int] = {
    "orgs": 1,
    "auth": 1,
    "storage": 1,
    "notifications": 1,
    "analytics": 2,
    "backups": 2,
    "billing": 3,
    "blog": 3,
    "crm": 3,
    "forms": 3,
    "listings": 3,
    "social": 3,
}

# Rule 4's one recorded exception to the app-config-walk ban: auth's
# undeclared-reconcile fallback, kept because deleting it changes which
# installed apps the anonymize boundary serves.  The technical audit tracks it
# (``account-deletion-hook-exception-text``); it retires on that watch item's
# trigger, and any second entry is a decision edit.  Each entry is
# ``(module, package file, attribute)``.
APP_CONFIG_WALK_SEAMS: frozenset[tuple[str, str, str]] = frozenset(
    {
        (
            "auth",
            "_account_deletion_providers.py",
            "reconcile_account_deletion_provider_state",
        ),
    }
)

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

# Rule 7's and rule 37's scan root for the generator's Jinja templates
# (enforcement gap 13): the mount and module-list detectors read these too.
GENERATOR_TEMPLATE_ROOT = "generator/templates/"


def _setting_name_module(attribute: str) -> str | None:
    """Return the module a QUICKSCALE_<MODULE>_* name belongs to, if any."""
    for module in MODULE_LAYERS:
        if attribute.startswith(f"QUICKSCALE_{module.upper()}_"):
            return module
    return None
