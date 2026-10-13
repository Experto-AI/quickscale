"""
Install/import probe for the SA267(d) split.

The runtime check creates an isolated temporary virtual environment, installs
the oldest claimed ``quickscale-core`` release plus the module's non-core
dependencies, and imports the module package and its core-importing
submodules.  The facade imports these names from this defining sibling, never
through the facade (decisions.md, Split-Facade Seams).  Behavior is unchanged
from the pre-split module.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _module_core_compat_versions import (
    _get_management_command_modules,
    _get_module_non_core_deps,
)


def _probe_module_install_import(
    mod_name: str,
    package_name: str,
    min_version: str,
    src_dir: Path,
    module_dir: Path,
) -> list[str]:
    """
    Run the install/import probe for one module.

    Returns a list of human-readable issues (empty = probe passed).
    """
    issues: list[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix=f"qs_compat_probe_{mod_name}_") as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            venv_path = tmpdir / ".venv"

            # --- create isolated venv ---
            log_prefix = "  INSTALL PROBE:"
            _log = lambda msg: print(f"  {log_prefix} {msg}")  # noqa: E731

            result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                issues.append(
                    f"{log_prefix} Failed to create virtual environment: {result.stderr.strip()}"
                )
                return issues

            pip_cmd = str(venv_path / "bin" / "pip")
            python_cmd = str(venv_path / "bin" / "python")

            # upgrade pip to avoid stale resolver warnings
            subprocess.run(
                [pip_cmd, "install", "--upgrade", "pip", "--quiet"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # --- install oldest claimed core ---
            _log(f"Installing quickscale-core=={min_version} ...")
            result = subprocess.run(
                [pip_cmd, "install", f"quickscale-core=={min_version}", "--quiet"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "No matching distribution" in stderr or "Could not find" in stderr:
                    _log(
                        f"quickscale-core=={min_version} not found on PyPI "
                        f"(may not be published yet) — skipping probe."
                    )
                else:
                    issues.append(
                        f"{log_prefix} Failed to install quickscale-core=={min_version}: {stderr}"
                    )
                return issues

            # --- install module deps (non-core) ---
            has_django = False
            extra_deps = _get_module_non_core_deps(module_dir)
            if extra_deps:
                has_django = any("Django" in d or "django" in d for d in extra_deps)
                _log("Installing module dependencies ...")
                result = subprocess.run(
                    [pip_cmd, "install", *extra_deps, "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode != 0:
                    issues.append(
                        f"{log_prefix} Failed to install module dependencies: "
                        f"{result.stderr.strip()}"
                    )

            # --- discover management command modules ---
            management_cmds = _get_management_command_modules(package_name, src_dir)

            # --- write probe script ---
            probe_script = tmpdir / "_probe.py"
            probe_script.write_text(
                _build_probe_script(
                    package_name=package_name,
                    src_dir=src_dir,
                    has_django=has_django,
                    management_commands=management_cmds,
                ),
                encoding="utf-8",
            )

            # --- execute probe ---
            probe_env = os.environ.copy()
            probe_env["PYTHONPATH"] = f"{src_dir}:{probe_env.get('PYTHONPATH', '')}"

            result = subprocess.run(
                [str(python_cmd), str(probe_script)],
                capture_output=True,
                text=True,
                timeout=60,
                env=probe_env,
            )

            # Interpret probe output
            probe_passed = False
            core_failure = False
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line == "PROBE_RESULT: PASS":
                    probe_passed = True
                elif line.startswith("PROBE_FAIL:"):
                    core_failure = True
                    issues.append(f"{log_prefix} {line[len('PROBE_FAIL:') :].strip()}")

            if result.returncode != 0 and not core_failure:
                # Non-zero exit but no PROBE_FAIL marker — likely a
                # Django config or other infrastructure issue.
                stderr = result.stderr.strip()
                if stderr:
                    _log(f"Probe script stderr (non-fatal): {stderr}")

            if probe_passed:
                _log(f"OK — {package_name} importable against quickscale-core=={min_version}")
            elif not core_failure:
                # Probe script ran but didn't reach PASS or FAIL marker
                issues.append(
                    f"{log_prefix} Probe script did not complete successfully "
                    f"(exit code {result.returncode})"
                )

    except subprocess.TimeoutExpired as exc:
        issues.append(f"  INSTALL PROBE: Probe timed out ({exc})")
    except Exception as exc:
        issues.append(f"  INSTALL PROBE: Unexpected error during probe: {exc}")

    return issues


def _build_probe_script(
    package_name: str,
    src_dir: Path,
    has_django: bool,
    management_commands: list[str] | None = None,
) -> str:
    """
    Build the probe script that will be run inside the isolated venv.

    The script writes PROBE_RESULT: PASS on success, or PROBE_FAIL: <msg>
    on failure.  Any other output is informational.

    *management_commands* is an optional list of dotted module paths for
    management command modules (e.g. ``["backups.management.commands.quickscale_backups_create"]``)
    that should be imported during the probe to verify they resolve.
    """
    lines: list[str] = [
        "import sys",
        f"sys.path.insert(0, {str(src_dir)!r})",
        "",
        "# Phase 1: import the top-level package",
        "try:",
        f"    import {package_name}",
        f'    print(f"OK: top-level {package_name} imported")',
        "except Exception as exc:",
        '    print(f"PROBE_FAIL: top-level import failed: {exc}")',
        "    sys.exit(1)",
        "",
    ]

    if has_django:
        lines += [
            "# Phase 2: configure Django settings for submodule probes",
            "import django",
            "from django.conf import settings",
            "# Minimal settings that let Django models load without a database",
            "settings.configure(",
            "    INSTALLED_APPS=[",
            f"        {package_name!r},",
            "    ],",
            "    DATABASES={",
            '        "default": {',
            '            "ENGINE": "django.db.backends.sqlite3",',
            '            "NAME": ":memory:",',
            "        }",
            "    },",
            "    USE_TZ=True,",
            "    # Allow any SECRET_KEY for the import test",
            '    SECRET_KEY="compat-probe-insecure-key",',
            ")",
            "django.setup()",
            "",
        ]

    # Phase 2b: probe core-importing submodules (services.py)
    services_mod = f"{package_name}.services"
    lines += [
        "# Phase 2b: probe core-importing submodules",
        f"for _mod in [{services_mod!r}]:",
        "    try:",
        "        __import__(_mod)",
        '        print(f"OK: {_mod} imported")',
        "    except ImportError as exc:",
        "        # Report quickscale_core import errors as failures",
        "        msg = str(exc)",
        '        if "quickscale_core" in msg or "quickscale" in msg.lower():',
        '            print(f"PROBE_FAIL: import {_mod} failed: {exc}")',
        "        else:",
        '            print(f"SKIP: {_mod} requires configuration: {exc}")',
        "    except Exception as exc:",
        "        if 'ImproperlyConfigured' in type(exc).__name__:",
        '            print(f"SKIP: {_mod} needs Django app config: {exc}")',
        "        elif hasattr(exc, '__module__') and 'django' in getattr(exc, '__module__', ''):",
        '            print(f"SKIP: {_mod} Django infrastructure: {exc}")',
        "        else:",
        '            print(f"PROBE_FAIL: import {_mod} failed: {exc}")',
    ]

    # Phase 3: probe management command modules (if any found)
    if management_commands:
        _cmd_list_repr = repr(management_commands)
        lines += [
            "",
            "# Phase 3: probe management command modules",
            f"for _cmd_mod in {_cmd_list_repr}:",
            "    try:",
            "        __import__(_cmd_mod)",
            '        print(f"OK: {_cmd_mod} imported")',
            "    except ImportError as exc:",
            "        msg = str(exc)",
            '        if "quickscale_core" in msg or "quickscale" in msg.lower():',
            '            print(f"PROBE_FAIL: import {_cmd_mod} failed: {exc}")',
            "        else:",
            '            print(f"SKIP: {_cmd_mod} requires configuration: {exc}")',
            "    except Exception as exc:",
            "        if 'ImproperlyConfigured' in type(exc).__name__:",
            '            print(f"SKIP: {_cmd_mod} needs Django app config: {exc}")',
            "        elif hasattr(exc, '__module__') and 'django'"
            " in getattr(exc, '__module__', ''):",
            '            print(f"SKIP: {_cmd_mod} Django infrastructure: {exc}")',
            "        else:",
            '            print(f"PROBE_FAIL: import {_cmd_mod} failed: {exc}")',
        ]

    # Success marker
    lines += [
        "",
        'print("PROBE_RESULT: PASS")',
    ]

    return "\n".join(lines)
