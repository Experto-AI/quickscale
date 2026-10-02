"""Railway CLI interaction utilities for deployment.

The implementation lives in private sibling modules grouped by concern
(``_railway_cli``, ``_railway_project``); this module re-exports every name
that previously lived here (Module Conventions rule 28), so existing
``quickscale_cli.utils.railway_utils`` imports and test patch targets keep
working unchanged.
"""

from __future__ import annotations

import json as json
import subprocess as subprocess
import time as time
from pathlib import Path as Path
from typing import Any as Any

from quickscale_core.utils.poetry_env import (
    build_isolated_poetry_env as build_isolated_poetry_env,
)

from quickscale_cli.utils._railway_cli import (
    _compare_versions as _compare_versions,
    check_railway_cli_version as check_railway_cli_version,
    deploy_railway_service as deploy_railway_service,
    get_railway_cli_version as get_railway_cli_version,
    get_railway_project_info as get_railway_project_info,
    install_railway_cli as install_railway_cli,
    is_npm_installed as is_npm_installed,
    is_railway_authenticated as is_railway_authenticated,
    is_railway_cli_installed as is_railway_cli_installed,
    is_railway_project_initialized as is_railway_project_initialized,
    login_railway_cli_browserless as login_railway_cli_browserless,
    run_railway_command as run_railway_command,
    set_railway_variable as set_railway_variable,
    set_railway_variables_batch as set_railway_variables_batch,
    upgrade_railway_cli as upgrade_railway_cli,
)
from quickscale_cli.utils._railway_project import (
    _get_railway_variables_json as _get_railway_variables_json,
    _is_non_retryable_database_link_error as _is_non_retryable_database_link_error,
    check_poetry_lock_consistency as check_poetry_lock_consistency,
    check_uncommitted_changes as check_uncommitted_changes,
    fix_poetry_lock as fix_poetry_lock,
    generate_django_secret_key as generate_django_secret_key,
    generate_railway_domain as generate_railway_domain,
    get_app_service_name as get_app_service_name,
    get_deployment_url as get_deployment_url,
    get_railway_variables as get_railway_variables,
    link_database_to_service as link_database_to_service,
    verify_dockerfile as verify_dockerfile,
    verify_railway_dependencies as verify_railway_dependencies,
    verify_railway_json as verify_railway_json,
)
