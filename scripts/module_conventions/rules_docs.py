"""README content rule."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from scripts.module_conventions.core import Corpus


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
    return violations
