"""
Model rules: tenancy, model basics, constraint and index names.

The mechanics live in private sibling modules (``_models_tenancy``,
``_models_basics``, ``_models_constraints``); this module orchestrates rules
13, 14, and 25 and re-exports every moved name so existing import paths and
the rule registry keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``re``, ``Mapping``, ``Corpus``, and core's helpers); the redundant
# aliases keep every one importable from this facade.
import ast as ast
import re as re
from collections.abc import Mapping as Mapping

from scripts.module_conventions._models_basics import (
    _AUTH_MODEL_BASES,
    _CAMEL_TO_SPACES,
    ALLOWED_DERIVED_CHOICE_NAMES,
    SINGLETON_ORDERING_EXEMPTIONS,
    _assignment_targets,
    _builder_bindings,
    _choice_list_violations,
    _defines_ordering,
    _defines_str,
    _django_default_verbose_name,
    _file_field_class_names,
    _gettext_violations,
    _inherits_ordering,
    _inherits_str,
    _is_abstract,
    _model_basics_classes,
    _model_meta_violations,
    _model_presentation_violations,
    _module_file,
    _path_suffix_reads,
    _resolve_upload_to_builder,
    _upload_extension_violations,
    _upload_to_builders,
    _user_relation_violations,
    _uuid_primary_key_violations,
)
from scripts.module_conventions._models_constraints import (
    _abstract_meta_calls,
    _check_constraint_names_checked_field,
    _check_purpose_names_fields,
    _condition_tokens,
    _constraint_call_violations,
    _constraint_owners,
    _duplicate_keyword_violations,
    _literal_field_tokens,
    _token_matches,
)
from scripts.module_conventions._models_tenancy import (
    _tenant_meta_violations,
    _tenant_reference_violations,
)
from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES as MODULE_ABSTRACT_BASES,
)
from scripts.module_conventions.core import (
    Corpus,
    _call_func_name,
    _parse,
)
from scripts.module_conventions.core import (
    Module as Module,
)
from scripts.module_conventions.core import (
    _ancestors as _ancestors,
)
from scripts.module_conventions.core import (
    _attribute_chain as _attribute_chain,
)
from scripts.module_conventions.core import (
    _class_names as _class_names,
)
from scripts.module_conventions.core import (
    _import_package_parts as _import_package_parts,
)
from scripts.module_conventions.core import (
    _keyword as _keyword,
)
from scripts.module_conventions.core import (
    _literal as _literal,
)
from scripts.module_conventions.core import (
    _meta_class as _meta_class,
)
from scripts.module_conventions.core import (
    _model_classes as _model_classes,
)
from scripts.module_conventions.core import (
    _uses_name as _uses_name,
)

#: The rule 40 harness re-exports every name the pre-split module published,
#: private helpers included: existing import paths (``registry``,
#: ``check_module_conventions``, the control cases) keep resolving through this
#: facade.
__all__ = (
    "ALLOWED_DERIVED_CHOICE_NAMES",
    "SINGLETON_ORDERING_EXEMPTIONS",
    "_AUTH_MODEL_BASES",
    "_CAMEL_TO_SPACES",
    "_abstract_meta_calls",
    "_assignment_targets",
    "_builder_bindings",
    "_check_constraint_names_checked_field",
    "_check_purpose_names_fields",
    "_condition_tokens",
    "_constraint_owners",
    "_defines_ordering",
    "_defines_str",
    "_django_default_verbose_name",
    "_file_field_class_names",
    "_inherits_ordering",
    "_inherits_str",
    "_is_abstract",
    "_literal_field_tokens",
    "_model_basics_classes",
    "_module_file",
    "_path_suffix_reads",
    "_resolve_upload_to_builder",
    "_token_matches",
    "_upload_to_builders",
    "rule_13_tenant_models",
    "rule_14_model_basics",
    "rule_25_constraint_names",
)


def rule_13_tenant_models(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            if module.name != "orgs":
                violations.extend(_tenant_reference_violations(module.name, rel, _parse(text)))
            if rel != "models.py":
                continue
            violations.extend(_tenant_meta_violations(module.name, _parse(text)))
    return violations


def rule_14_model_basics(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            violations.extend(_gettext_violations(module.name, rel, _parse(text)))
        models = module.files.get("models.py")
        if models is None:
            continue
        tree = _parse(models)
        field_class_names = _file_field_class_names(module)
        violations.extend(_upload_extension_violations(module, tree, field_class_names))
        violations.extend(_choice_list_violations(module.name, tree))
        violations.extend(_user_relation_violations(module.name, stem, tree))
        violations.extend(_uuid_primary_key_violations(module.name, tree))
        violations.extend(_model_meta_violations(module.name, tree))
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        violations.extend(_model_presentation_violations(module.name, tree, classes))
    return violations


def rule_25_constraint_names(corpus: Corpus) -> list[str]:
    """Rule 25: every constraint and index sets a stemmed name."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            violations.extend(_duplicate_keyword_violations(module.name, rel, tree))
            abstract_calls = _abstract_meta_calls(tree)
            owners = _constraint_owners(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                kind = _call_func_name(node)
                if kind not in {"UniqueConstraint", "CheckConstraint", "Index"}:
                    continue
                violations.extend(
                    _constraint_call_violations(
                        module.name, rel, node, kind, abstract_calls, owners
                    )
                )
    return violations
