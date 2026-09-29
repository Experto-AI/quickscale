#!/usr/bin/env python3
"""
Render a Jinja2 template with lint-optimized dummy context.

Replaces the sed-based render_template() in lint_frontend.sh.
Handles all Jinja2 constructs: {% if %}, {% for %}, {% set %},
{% raw %}...{% endraw %}, whitespace control, {{ variables }}, etc.

Usage: render_j2_template.py <source.j2> <destination>
       render_j2_template.py --list-modules [--exclude MODULE]

``--list-modules`` prints the discovered shipped module names as a JSON
array (minus ``--exclude`` when given) so the lint pipeline derives its
``selected_modules`` variants from one discovery implementation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _discover_modules() -> list[str]:
    """
    Return the shipped module names, discovered from quickscale_modules.

    The workspace's ``module.yml`` files are the module inventory (Module
    Conventions rule 37), so a module added to the repository joins the lint
    context without editing this script.  Discovery fails closed: a missing
    workspace, an empty workspace, or a directory without a ``module.yml``
    (Module Conventions rule 18) is an error rather than a silently shrunken
    module set.
    """
    modules_dir = Path(__file__).resolve().parents[1] / "quickscale_modules"
    if not modules_dir.is_dir():
        raise SystemExit(f"Error: module workspace not found: {modules_dir}")
    modules: list[str] = []
    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not (entry / "module.yml").is_file():
            raise SystemExit(f"Error: module directory without module.yml: {entry}")
        modules.append(entry.name)
    if not modules:
        raise SystemExit(f"Error: no module manifests found under {modules_dir}")
    return modules


def get_lint_context() -> dict:
    """
    Return rendering context that produces maximal lint coverage.

    Strategy: treat all module features as enabled so that ESLint and
    TypeScript can validate every code path in the rendered output.
    """
    _all_modules = _discover_modules()

    # Allow SELECTED_MODULES env var override so the lint pipeline can
    # render a no-social variant for TypeScript validation coverage.
    env_modules = os.environ.get("SELECTED_MODULES")
    if env_modules is not None:
        try:
            modules = json.loads(env_modules)
        except json.JSONDecodeError as exc:
            print(
                f"Warning: SELECTED_MODULES is not valid JSON ({exc}), "
                "falling back to all modules.",
                file=sys.stderr,
            )
            modules = _all_modules
    else:
        modules = _all_modules

    return {
        "project_name": "MyApp",
        "package_name": "myapp",
        "project_description": "A QuickScale project",
        # Full module list so 'foo in selected_modules' is always True
        # and 'selected_modules is none' is False for maximal coverage.
        "selected_modules": modules,
    }


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--list-modules"]:
        exclude = None
        if len(args) > 1:
            if len(args) != 3 or args[1] != "--exclude":
                print(
                    f"Usage: {sys.argv[0]} --list-modules [--exclude MODULE]",
                    file=sys.stderr,
                )
                sys.exit(1)
            exclude = args[2]
        print(json.dumps([name for name in _discover_modules() if name != exclude]))
        return

    if len(args) != 2:
        print(
            f"Usage: {sys.argv[0]} <source.j2> <destination>"
            f" | {sys.argv[0]} --list-modules [--exclude MODULE]",
            file=sys.stderr,
        )
        sys.exit(1)

    src = args[0]
    dest = args[1]

    # Read the template source
    try:
        with open(src) as f:
            template_source = f.read()
    except FileNotFoundError:
        print(f"Error: source file not found: {src}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {src}: {e}", file=sys.stderr)
        sys.exit(1)

    # Import lazily — fail with a clear message if Jinja2 isn't available
    try:
        from jinja2 import Environment, Undefined
    except ImportError:
        print(
            "Error: Jinja2 is not installed. Run: poetry install",
            file=sys.stderr,
        )
        sys.exit(1)

    env = Environment(
        # Silently resolve unknown variables to empty string so templates
        # that reference variables we haven't provided still render cleanly.
        undefined=Undefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    try:
        rendered = env.from_string(template_source).render(**get_lint_context())
    except Exception as e:
        print(f"Error rendering {src}: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure destination directory exists
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        with open(dest, "w") as f:
            f.write(rendered)
    except OSError as e:
        print(f"Error writing {dest}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
