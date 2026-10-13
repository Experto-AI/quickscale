"""
Rules 20 (direct email), 45 (stub exemptions), and 50 (notification links).

Implementation detail of :mod:`scripts.module_conventions.rules_misc`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Mapping

from scripts.module_conventions.core import (
    Corpus,
    _call_func_name,
    _parse,
)


def rule_20_email(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        if module.name == "notifications":
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            imports_mail = any(
                isinstance(node, ast.Import)
                and any(alias.name == "django.core.mail" for alias in node.names)
                or isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("django.core.mail")
                for node in ast.walk(tree)
            )
            calls_mail = any(
                isinstance(node, ast.Call)
                and _call_func_name(node)
                in {
                    "send_mail",
                    "EmailMessage",
                    "EmailMultiAlternatives",
                    "get_connection",
                }
                for node in ast.walk(tree)
            )
            if imports_mail or calls_mail:
                violations.append(f"rule 20: {module.name}: {rel} sends email directly")
        if "send_notification" in "".join(module.files.values()):
            required = module.manifest.get("required_modules")
            if not isinstance(required, list):
                required = []
            if "notifications" not in required:
                violations.append(
                    f"rule 20: {module.name}: calls send_notification "
                    "without requiring notifications"
                )
    return violations


def _mapping_key_writes(tree: ast.Module, key: str) -> list[int]:
    """Return the line numbers where *key* is written as a mapping key."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for dict_key in node.keys:
                if isinstance(dict_key, ast.Constant) and dict_key.value == key:
                    lines.append(dict_key.lineno)
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if isinstance(node.slice, ast.Constant) and node.slice.value == key:
                lines.append(node.lineno)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == key:
                    lines.append(keyword.value.lineno)
    return lines


def rule_50_notification_links(corpus: Corpus) -> list[str]:
    """Rule 50: a sender declares whom a notification is about, never by key."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in sorted(module.files.items()):
            if not rel.endswith(".py"):
                continue
            for lineno in _mapping_key_writes(_parse(text), "actor_user_id"):
                violations.append(
                    f"rule 50: {module.name}: {rel}:{lineno} writes the reserved "
                    "notification person-link key 'actor_user_id' in module source; "
                    "pass send_notification(about_users=...) instead"
                )
    return violations


def rule_45_stub_exemptions(corpus: Corpus) -> list[str]:
    """Rule 45: third-party stub exemptions live in the root ``mypy.ini`` only."""
    violations: list[str] = []
    for module in corpus.modules:
        pyproject = module.root_files.get("pyproject.toml")
        if pyproject is None:
            continue
        try:
            data = tomllib.loads(pyproject)
        except tomllib.TOMLDecodeError:
            # Rule 18 reports the unparsable file.
            continue
        tool = data.get("tool")
        mypy = tool.get("mypy") if isinstance(tool, Mapping) else None
        if isinstance(mypy, Mapping):
            violations.append(
                f"rule 45: {module.name}: pyproject.toml declares a per-module [tool.mypy] table"
            )
    return violations
