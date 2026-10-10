"""README content rule."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from scripts.module_conventions.core import Corpus, Module

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


def rule_38_readme_content(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    required_headings = (
        "Overview",
        "Configuration",
        "Public surface",
        "URLs",
        "Management commands",
        "Operations",
        "Extending",
    )
    for module in corpus.modules:
        readme = module.root_files.get("README.md")
        if readme is None:
            violations.append(f"rule 38: {module.name}: README.md is missing")
            continue
        headings = re.findall(r"^##\s+(.+?)\s*$", readme, re.MULTILINE)
        position = 0
        for heading in required_headings:
            try:
                position = headings.index(heading, position) + 1
            except ValueError:
                violations.append(f"rule 38: {module.name}: README heading {heading!r} missing")
                break
        for heading in headings:
            if re.search(r"\d+\.\d+", heading):
                violations.append(
                    f"rule 38: {module.name}: README heading {heading!r} has a version"
                )
        sections: dict[str, str] = {}
        current = ""
        for line in readme.splitlines():
            match = re.match(r"^##\s+(.+?)\s*$", line)
            if match:
                current = match.group(1)
                sections.setdefault(current, "")
                continue
            if current:
                sections[current] += line + "\n"
        configuration = sections.get("Configuration", "")
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
        commands = sections.get("Management commands", "")
        for rel in module.files:
            if not rel.startswith("management/commands/"):
                continue
            command = Path(rel).stem
            if command == "__init__":
                continue
            if command not in commands:
                violations.append(
                    f"rule 38: {module.name}: Management commands does not name {command!r}"
                )
        if _uses_org_roles(module):
            public_surface = sections.get("Public surface", "")
            if not _lists_role_requirement(public_surface):
                violations.append(
                    f"rule 38: {module.name}: Public surface does not list the minimum role"
                )
    return violations
