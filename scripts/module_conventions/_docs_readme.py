"""
README content rule mechanics.

Rule 38's orchestration lives in ``rules_docs``; that module re-exports every
name defined here, so existing import paths and the rule registry keep
working.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from scripts.module_conventions._package_commands import _command_flags
from scripts.module_conventions.core import Module, _parse

#: Rule 38's role-listing trigger: the orgs role tools a module's views use.
_ORG_ROLE_TOKENS = re.compile(r"\b(?:HasOrgRole|OrgRoleMixin|min_org_role|user_has_org_role)\b")

#: Rule 38's minimum-role declaration: an identifiable role requirement — a
#: backticked role value or a role value beside the word "role" — so an
#: incidental mention ("Django admin", "member management") is not a listing.
_ROLE_LISTING = re.compile(
    r"`(?:viewer|member|admin|owner)`"
    r"|\brole\b.{0,12}\b(?:viewer|member|admin|owner)\b"
    r"|\b(?:viewer|member|admin|owner)\b.{0,12}\brole\b",
    re.IGNORECASE,
)

#: Rule 38's role table: a header cell naming roles and a body cell whose
#: value is exactly a role.
_ROLE_TABLE_HEADER = re.compile(r"\broles?\b", re.IGNORECASE)
_ROLE_TABLE_VALUE = re.compile(r"(?:viewer|member|admin|owner)", re.IGNORECASE)

#: Rule 38's required README level-two headings, in order.
REQUIRED_HEADINGS = (
    "Overview",
    "Configuration",
    "Public surface",
    "URLs",
    "Management commands",
    "Operations",
    "Extending",
)

#: A level-two heading line: ``## <heading>``.
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

#: A version number inside a heading, e.g. ``2.0`` in ``## 2.0 Notes``.
_VERSIONED_HEADING = re.compile(r"\d+\.\d+")


def _lists_role_requirement(section: str) -> bool:
    """
    Return whether a section carries an identifiable role requirement.

    An inline declaration is a backticked role value or a role value beside
    the word "role"; a table declares it with a header cell naming roles and
    a body cell whose value is exactly a role, backticked or not.
    """
    if _ROLE_LISTING.search(section):
        return True
    header_names_roles = False
    in_table = False
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            in_table = False
            header_names_roles = False
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if not in_table:
            in_table = True
            header_names_roles = any(_ROLE_TABLE_HEADER.search(cell) for cell in cells)
            continue
        if header_names_roles and any(_ROLE_TABLE_VALUE.fullmatch(cell) for cell in cells):
            return True
    return False


def _uses_org_roles(module: Module) -> bool:
    """Return whether the module's source authorizes through orgs' role tools."""
    for rel, text in module.files.items():
        if rel.endswith(".py") and not rel.startswith("migrations/"):
            if _ORG_ROLE_TOKENS.search(text):
                return True
    return False


def _readme_headings(readme: str) -> list[str]:
    """Return the README's level-two headings in document order."""
    return _HEADING.findall(readme)


def _heading_violations(module: Module, headings: list[str]) -> list[str]:
    """Return one finding for the first required heading missing in order."""
    violations: list[str] = []
    position = 0
    for heading in REQUIRED_HEADINGS:
        try:
            position = headings.index(heading, position) + 1
        except ValueError:
            violations.append(f"rule 38: {module.name}: README heading {heading!r} missing")
            break
    return violations


def _versioned_heading_violations(module: Module, headings: list[str]) -> list[str]:
    """Return one finding per heading that carries a version number."""
    return [
        f"rule 38: {module.name}: README heading {heading!r} has a version"
        for heading in headings
        if _VERSIONED_HEADING.search(heading)
    ]


def _readme_sections(readme: str) -> dict[str, str]:
    """Return each level-two section's body keyed by its heading."""
    sections: dict[str, str] = {}
    current = ""
    for line in readme.splitlines():
        match = _HEADING.match(line)
        if match:
            current = match.group(1)
            sections.setdefault(current, "")
            continue
        if current:
            sections[current] += line + "\n"
    return sections


def _configuration_violations(module: Module, configuration: str) -> list[str]:
    """Return one finding per manifest option the Configuration section omits."""
    violations: list[str] = []
    config = module.manifest.get("config")
    if not isinstance(config, Mapping):
        config = {}
    for kind in ("mutable", "immutable"):
        options = config.get(kind)
        if not isinstance(options, Mapping):
            continue
        for key in options:
            if not isinstance(key, str):
                continue
            if key not in configuration:
                violations.append(
                    f"rule 38: {module.name}: Configuration does not name option {key!r}"
                )
    return violations


def _command_violations(module: Module, commands: str) -> list[str]:
    """Return one finding per management command the section omits."""
    violations: list[str] = []
    for rel in module.files:
        if not rel.startswith("management/commands/"):
            continue
        command = Path(rel).stem
        if command == "__init__" or command.startswith("_"):
            # Django discovers commands as non-underscore modules in the
            # commands package, so a private support module is not a command.
            continue
        if command not in commands:
            violations.append(
                f"rule 38: {module.name}: Management commands does not name {command!r}"
            )
    return violations


def _command_option_strings(text: str) -> set[str]:
    """
    Return the flags a command module's ``add_argument`` calls declare.

    Rule 17's ``_command_flags`` maps every literal ``add_argument`` argument,
    positionals included; the flags are its ``-``-prefixed subset.
    """
    return {flag for flag in _command_flags(_parse(text)) if flag.startswith("-")}


def _flag_violations(module: Module, commands: str) -> list[str]:
    """Return one finding per command flag the Management commands section omits."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.startswith("management/commands/") or not rel.endswith(".py"):
            continue
        command = Path(rel).stem
        if command == "__init__" or command.startswith("_"):
            continue
        for flag in sorted(_command_option_strings(text)):
            if flag not in commands:
                violations.append(
                    f"rule 38: {module.name}: Management commands does not name flag {flag!r}"
                )
    return violations


def _role_listing_violations(module: Module, public_surface: str) -> list[str]:
    """Return the role-listing finding for a module that uses orgs' role tools."""
    if _uses_org_roles(module) and not _lists_role_requirement(public_surface):
        return [f"rule 38: {module.name}: Public surface does not list the minimum role"]
    return []


def _readme_violations(module: Module) -> list[str]:
    """Return rule 38's findings for one module, in the pre-split order."""
    readme = module.root_files.get("README.md")
    if readme is None:
        return [f"rule 38: {module.name}: README.md is missing"]
    headings = _readme_headings(readme)
    sections = _readme_sections(readme)
    commands = sections.get("Management commands", "")
    return [
        *_heading_violations(module, headings),
        *_versioned_heading_violations(module, headings),
        *_configuration_violations(module, sections.get("Configuration", "")),
        *_command_violations(module, commands),
        *_flag_violations(module, commands),
        *_role_listing_violations(module, sections.get("Public surface", "")),
    ]
