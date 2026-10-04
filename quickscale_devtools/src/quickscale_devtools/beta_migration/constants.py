"""Constants, path inventories, and static grammars for beta migration."""

from .model import BetaMigrationMode, RequiredPathSpec, VerificationCommandSpec
import re


PHASE_BOUNDARY_REASON = (
    "Mutation, merge, apply, verification execution, and deployment steps remain intentionally "
    "non-destructive in this phase."
)


DRY_RUN_REASON = (
    "Dry run requested. Planned actions were reported without mutating donor or recipient files "
    "and without executing verification commands."
)


MANUAL_HANDOFF_REASON = (
    "Local automation stops after deterministic file operations and verification. Smoke testing, "
    "repo replacement, PR/merge, deploy, env vars, and rollback remain explicit operator steps."
)


FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES = (
    "urls.py",
    "views.py",
    "context_processors.py",
    "settings/production.py",
)


FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES = (
    "asgi.py",
    "wsgi.py",
    "settings/base.py",
    "settings/local.py",
    "settings/modules.py",
    "urls_modules.py",
)


FRESH_FIRST_OPTIONAL_DONOR_PACKAGE_FILES = (
    "middleware.py",
    "sitemaps.py",
)


FRESH_FIRST_IDENTITY_ROOT_FILES = (
    ".env",
    ".env.example",
    ".github/workflows/ci.yml",
    "manage.py",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
    "start.sh",
    "README.md",
    "OPERATIONS.md",
    "db/init.sql",
    "scripts/lint.sh",
    "tests/conftest.py",
    "tests/test_example.py",
    "frontend/package.json",
    "frontend/e2e/home.spec.ts",
    "frontend/src/hooks/useModules.ts",
    "templates/404.html",
    "templates/500.html",
    "templates/base.html",
    "templates/index.html",
    "templates/social/link_tree.html",
    "templates/social/embeds.html",
)


FRESH_FIRST_IDENTITY_PACKAGE_FILES = (
    "__init__.py",
    "asgi.py",
    "wsgi.py",
    "settings/__init__.py",
    "settings/base.py",
    "settings/local.py",
)


FRESH_FIRST_DONOR_DJANGO_FILES = (
    "urls.py",
    "views.py",
    "middleware.py",
    "sitemaps.py",
    "context_processors.py",
    "settings/production.py",
)


FRESH_FIRST_UTILITY_DIRS = (
    "assets",
    "data",
    "types",
    "stores",
)


FRESH_FIRST_COMPONENT_DIR_SKIP = {"ui"}


FRESH_FIRST_REPLACED_ROOT_FILES = ("frontend/src/App.tsx",)


FRESH_FIRST_COPY_MISSING_DIRS = ("frontend/src/pages",)


FRESH_FIRST_MERGED_ROOT_FILES = ("pyproject.toml", "frontend/package.json")


# The showcase_react theme's project-owned design layer (SA214 slice d). The
# migration ports the donor's design into this layer; upgrades and applies
# never overwrite it, and it is the one design source for React and the
# Django-rendered shell.
DESIGN_LAYER_RELATIVE_DIR = "frontend/design"


# Legacy donors (generated before the design layer existed) carried the design
# in the Tailwind entry stylesheet and the Tailwind config. Each pair maps the
# donor source to its design-layer entry point.
DESIGN_LAYER_LEGACY_SOURCES = (
    ("frontend/src/index.css", "frontend/design/tokens.css"),
    ("frontend/tailwind.config.js", "frontend/design/tailwind.preset.js"),
)


# The generated ``settings/base.py`` ends its INSTALLED_APPS literal with this
# comment; project-owned apps are registered immediately above it.
INSTALLED_APPS_APPEND_SENTINEL = "# Add your apps here"


FRESH_FIRST_PROTECTED_PACKAGE_FILES = (
    "settings/modules.py",
    "urls_modules.py",
    "settings/base.py",
    "settings/local.py",
)


FRESH_FIRST_PROTECTED_ROOT_FILES = ("railway.json",)


# ---- Donor-file classification inventory (SA214 slice b) ----
# Every donor file lands in exactly one migration class. Build artifacts are
# never carried between trees and are pruned from the donor walk; the tuples
# below are path rules, not copy targets.

DONOR_ARTIFACT_DIR_COMPONENTS: tuple[str, ...] = (
    ".cache",
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "htmlcov",
    "node_modules",
    "venv",
)

DONOR_ARTIFACT_ROOT_DIRS: tuple[str, ...] = (
    ".quickscale",
    "dist",
    "media",
    "staticfiles",
)

DONOR_ARTIFACT_PATH_PREFIXES: tuple[str, ...] = ("frontend/dist",)

DONOR_ARTIFACT_NAMES: tuple[str, ...] = (
    ".DS_Store",
    ".coverage",
    ".env",
    "Thumbs.db",
)

DONOR_ARTIFACT_ROOT_FILES: tuple[str, ...] = ("poetry.lock",)

DONOR_ARTIFACT_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo")

DONOR_ENV_FILE_PREFIX = ".env."

DONOR_ENV_FILE_EXEMPT = ".env.example"

DONOR_RECOGNIZED_PROJECT_DIRS: tuple[str, ...] = (
    ".github",
    "db",
    "frontend",
    "scripts",
    "static",
    "templates",
    "tests",
)

DONOR_RECOGNIZED_PROJECT_ROOT_FILES: tuple[str, ...] = ("quickscale.yml",)


INTENTIONALLY_UNMANAGED: tuple[str, ...] = (
    # ---- Project-level user-owned files ----
    # Root-level generated files that are one-time scaffold and
    # user-editable after generation. Existing files are not structurally
    # replaced or merged; entries may still receive copy-if-missing adoption or
    # the fresh scaffold's one-time field-aware identity reconciliation.
    "Makefile",
    "README.md",
    ".gitignore",
    ".dockerignore",
    ".editorconfig",
    ".pre-commit-config.yaml",
    ".env.example",
    ".env",
    "scripts/lint.sh",
    ".github/workflows/ci.yml",
    "poetry.lock",
    "db/init.sql",
    "OPERATIONS.md",
    # ---- Package __init__ files ----
    # Generated Django package markers. Fresh-first renames the package
    # directory and rewrites the project-slug docstrings without replacing
    # either file from another project.
    "{package}/__init__.py",
    "{package}/settings/__init__.py",
    # ---- User Django templates ----
    # All generated templates under templates/ are user-editable
    # Django templates.  Unlike infrastructure files (Dockerfile,
    # start.sh), they are not copy targets during migration.  Fresh-first
    # preserves the recipient's templates as generated.
    "templates/404.html",
    "templates/500.html",
    "templates/base.html",
    "templates/index.html",
    "templates/admin/index.html",
    "templates/admin/app_index.html",
    "templates/social/link_tree.html",
    "templates/social/embeds.html",
    # ---- User test scaffolding ----
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_example.py",
    # ---- Frontend root configs (user-owned after generation) ----
    # Generated once, user-editable, and not migration targets.  The
    # frontend build configs (vite, tsconfig, eslint, postcss) are kept
    # exactly as the fresh scaffold emitted them.  The design layer is listed
    # below with its own never-overwritten guarantee.
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/eslint.config.js",
    "frontend/postcss.config.js",
    "frontend/pnpm-workspace.yaml",
    "frontend/.prettierignore",
    "frontend/.prettierrc",
    "frontend/vitest.config.ts",
    "frontend/playwright.config.ts",
    "frontend/components.json",
    "frontend/tailwind.config.js",
    "frontend/index.html",
    "frontend/public/favicon.svg",
    # ---- Project-owned design layer (never overwritten) ----
    # One folder holding the tokens stylesheet, the Tailwind preset, fonts,
    # and brand assets.  No upgrade or ``quickscale apply`` ever replaces or
    # merges these files; the beta-migration tool copies the donor's design
    # into them once, and the project edits them freely afterwards.
    "frontend/design/",
    # ---- Frontend user-owned source files ----
    # Files under frontend/src/ are user-editable application code.
    # Specific files may be migration targets (App.tsx is replaced in
    # fresh-first; useModules.ts follows the reconciled scaffold identity);
    # those are in the managed tuples.  Everything else stays with the user.
    "frontend/src/main.tsx",
    "frontend/src/renderQuickScaleRoot.tsx",
    "frontend/src/index.css",
    "frontend/src/vite-env.d.ts",
    "frontend/src/posthog-js.d.ts",
    "frontend/src/lib/utils.ts",
    "frontend/src/lib/analytics.ts",
    "frontend/src/lib/csrf.ts",
    "frontend/src/lib/validateQuickScaleSeam.ts",
    "frontend/src/test/setup.ts",
    "frontend/src/test/App.test.tsx",
    "frontend/src/test/csrf.test.tsx",
    "frontend/src/test/validateQuickScaleSeam.test.ts",
    "frontend/src/test/viteAssetRouting.test.ts",
    "frontend/src/test/RootDispatch.test.tsx",
    "frontend/src/test/PublicSocialPages.test.tsx",
    "frontend/src/test/useApiErrors.test.ts",
    "frontend/src/test/FormRenderer.test.tsx",
    "frontend/e2e/home.spec.ts",
    # ---- shadcn/ui components (user-owned after generation) ----
    "frontend/src/components/ui/checkbox.tsx",
    "frontend/src/components/ui/radio-group.tsx",
    "frontend/src/components/ui/form.tsx",
    "frontend/src/components/ui/card.tsx",
    "frontend/src/components/ui/textarea.tsx",
    "frontend/src/components/ui/input.tsx",
    "frontend/src/components/ui/separator.tsx",
    "frontend/src/components/ui/label.tsx",
    "frontend/src/components/ui/button.tsx",
    "frontend/src/components/ui/badge.tsx",
    "frontend/src/components/ui/tooltip.tsx",
    "frontend/src/components/ui/select.tsx",
    # ---- Non-module pages ----
    "frontend/src/pages/Dashboard.tsx",
    "frontend/src/pages/NotFound.tsx",
    "frontend/src/pages/ProfilePage.tsx",
    "frontend/src/pages/SettingsPage.tsx",
    # ---- Module-conditional pages (user-owned after generation) ----
    # These pages are emitted only when the gating module is selected.
    # After generation they are user-editable and are not structurally
    # managed; donor-only copies may still be adopted through the explicit
    # copy-if-missing walk, which never overwrites an existing user file.
    "frontend/src/pages/BlogPage.tsx",
    "frontend/src/pages/CrmPage.tsx",
    "frontend/src/pages/ListingsPage.tsx",
    "frontend/src/pages/FormsPage.tsx",
    "frontend/src/pages/SocialLinkTreePublicPage.tsx",
    "frontend/src/pages/SocialEmbedsPublicPage.tsx",
    # ---- Org pages (always emitted for React theme) ----
    "frontend/src/pages/orgs/OrgLayout.tsx",
    "frontend/src/pages/orgs/OrgDashboardPage.tsx",
    "frontend/src/pages/orgs/OrgMembersPage.tsx",
    "frontend/src/pages/orgs/OrgSettingsPage.tsx",
    "frontend/src/pages/orgs/OrgCreatePage.tsx",
    "frontend/src/pages/orgs/OrgListPage.tsx",
    # ---- Non-infrastructure hooks ----
    "frontend/src/hooks/useOrgNavigation.ts",
    "frontend/src/hooks/useOrgs.ts",
    "frontend/src/hooks/useApi.ts",
    "frontend/src/hooks/useFormSchema.ts",
    "frontend/src/hooks/usePublicSocialSurface.ts",
)


COMMON_REQUIRED_SPECS = {
    "donor": (
        RequiredPathSpec(
            "quickscale.yml", "file", "QuickScale desired-state configuration"
        ),
        RequiredPathSpec("pyproject.toml", "file", "Poetry project metadata"),
        RequiredPathSpec(
            "frontend/package.json", "file", "React frontend package manifest"
        ),
    ),
    "recipient": (
        RequiredPathSpec(
            "quickscale.yml", "file", "QuickScale desired-state configuration"
        ),
        RequiredPathSpec("pyproject.toml", "file", "Poetry project metadata"),
        RequiredPathSpec(
            "frontend/package.json", "file", "React frontend package manifest"
        ),
    ),
}


_FRESH_FIRST_MODE_REQUIRED_SPECS: dict[str, tuple[RequiredPathSpec, ...]] = {
    "donor": (
        RequiredPathSpec("frontend/src/App.tsx", "file", "custom router source"),
        RequiredPathSpec("frontend/src/pages", "dir", "custom page directory"),
        RequiredPathSpec(
            "frontend/src/components", "dir", "custom component directory"
        ),
    ),
    "recipient": (
        RequiredPathSpec("manage.py", "file", "Django manage.py entrypoint"),
        RequiredPathSpec("Dockerfile", "file", "fresh scaffold Dockerfile"),
        RequiredPathSpec("docker-compose.yml", "file", "fresh scaffold compose file"),
        RequiredPathSpec("start.sh", "file", "fresh scaffold runtime launcher"),
        RequiredPathSpec("railway.json", "file", "fresh scaffold Railway metadata"),
        RequiredPathSpec(
            "frontend/src/App.tsx", "file", "fresh scaffold router source"
        ),
        RequiredPathSpec("frontend/src/pages", "dir", "fresh scaffold page directory"),
        RequiredPathSpec(
            "frontend/src/components", "dir", "fresh scaffold component directory"
        ),
        RequiredPathSpec(
            "frontend/src/hooks/useModules.ts",
            "file",
            "fresh scaffold managed modules hook",
        ),
    ),
}


MODE_REQUIRED_SPECS: dict[
    BetaMigrationMode, dict[str, tuple[RequiredPathSpec, ...]]
] = {
    # The iterate mode regenerates the recipient from the donor's quickscale.yml
    # and then runs the same fresh-first mutation, so both modes require the
    # same donor and recipient surfaces.
    "fresh-first": _FRESH_FIRST_MODE_REQUIRED_SPECS,
    "iterate": _FRESH_FIRST_MODE_REQUIRED_SPECS,
}


# The recipient regeneration step runs the shipped apply command from a staging
# directory named after the slug, exactly as the migration playbook does. A
# fresh project with --no-docker still asks two confirmation questions: the
# apply gate and the destructive/remote-phase gate. Answer both with "yes" so
# the target stays non-interactive; any further prompt reaches EOF and aborts,
# so the workflow fails closed instead of guessing.
REGENERATION_APPLY_ARGV = (
    "quickscale",
    "apply",
    "--split-refs-from-branches",
    "--no-docker",
)

REGENERATION_APPLY_STDIN = "y\ny\n"

REGENERATION_APPLY_TIMEOUT_SECONDS = 1800


VERIFICATION_COMMAND_SPECS = (
    VerificationCommandSpec("poetry lock", ("poetry", "lock")),
    VerificationCommandSpec("poetry install", ("poetry", "install")),
    VerificationCommandSpec("pnpm install", ("pnpm", "install"), cwd_suffix="frontend"),
    VerificationCommandSpec("pnpm build", ("pnpm", "build"), cwd_suffix="frontend"),
    VerificationCommandSpec(
        "quickscale manage migrate", ("quickscale", "manage", "migrate")
    ),
    VerificationCommandSpec("pytest", ("pytest",)),
    VerificationCommandSpec("pnpm test", ("pnpm", "test"), cwd_suffix="frontend"),
)


VERIFICATION_COMMAND_TIMEOUT_SECONDS = 600


_RUNTIME_COMMAND_NAMES = frozenset(
    {"QUICKSCALE_PRIVILEGED_COMMAND", "QUICKSCALE_NON_DB_COMMAND"}
)


_RUNTIME_COMMAND_MARKER = re.compile(r"QUICKSCALE_.*_COMMAND")


_DYNAMIC_RUNTIME_COMMAND_MARKER = re.compile(r"\$[^\s=]*_COMMAND")


_SHELL_ENV_ASSIGNMENT = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)", re.DOTALL
)


_STATIC_RUNTIME_COMMAND = re.compile(r"[A-Za-z0-9_-]+")


_START_SH_PACKAGE_REFERENCE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.wsgi(?::application)?\b"
)


_STATIC_MANAGE_COMMAND = re.compile(r"\bpython(?:3)?\s+manage\.py\s+([A-Za-z0-9_-]+)\b")


_EXEC_SHELL_WORD = "exec"


_GUNICORN_SHELL_WORD = "gunicorn"


_REQUIRED_RUNTIME_COMMANDS: dict[str, frozenset[str]] = {
    "QUICKSCALE_PRIVILEGED_COMMAND": frozenset({"migrate", "createcachetable"}),
    "QUICKSCALE_NON_DB_COMMAND": frozenset({"collectstatic"}),
}


_UNCONDITIONAL_RUNTIME_COMMANDS: dict[str, frozenset[str]] = {
    "QUICKSCALE_PRIVILEGED_COMMAND": frozenset({"migrate"}),
    "QUICKSCALE_NON_DB_COMMAND": frozenset({"collectstatic"}),
}


_RUNTIME_COMMAND_LAUNCHERS = {
    "QUICKSCALE_PRIVILEGED_COMMAND": "start.sh",
    "QUICKSCALE_NON_DB_COMMAND": "Dockerfile",
}


_START_SH_COMMANDS = frozenset(
    {
        ":",
        "echo",
        "exit",
        "export",
        "false",
        "grep",
        "gunicorn",
        "pip",
        "python",
        "python3",
        "set",
        "true",
    }
)


_START_SH_CONTROL_MARKERS = frozenset({"do", "done", "else", "fi", "then"})


_SHELL_TEST_OPEN = "[["


_SHELL_TEST_CLOSE = "]]"


_SHELL_ARITHMETIC_OPEN = "(("


_START_SH_HEREDOC_IMPORTS = frozenset({"os", "psycopg2"})


_START_SH_HEREDOC_FROM_IMPORTS = {"psycopg2": frozenset({"sql"})}


_START_SH_HEREDOC_CALL_NAMES = frozenset({"SystemExit", "print"})


_START_SH_HEREDOC_CALL_ATTRIBUTES = frozenset(
    {
        "Identifier",
        "Literal",
        "SQL",
        "close",
        "connect",
        "cursor",
        "execute",
        "fetchone",
        "format",
        "get",
    }
)


_START_SH_INLINE_IMPORTS = frozenset({"os"})


_START_SH_INLINE_FROM_IMPORTS = {
    "django.conf": frozenset({"settings"}),
    "django.contrib.auth": frozenset({"get_user_model"}),
}


_START_SH_INLINE_CALL_NAMES = frozenset({"get_user_model", "print", "type"})


_START_SH_INLINE_CALL_ATTRIBUTES = frozenset({"create_superuser", "exists", "filter"})


_DOCKER_GENERATED_KEY_PAYLOAD = (
    "from secrets import token_urlsafe; print(token_urlsafe(50))"
)


_DOCKER_RUN_COMMANDS = frozenset(
    {
        "[",
        "apt-get",
        "break",
        "chmod",
        "chown",
        "corepack",
        "curl",
        "echo",
        "exit",
        "export",
        "groupadd",
        "install",
        "mkdir",
        "pip",
        "pnpm",
        "poetry",
        "python",
        "python3",
        "rm",
        "sleep",
        "timeout",
        "useradd",
    }
)


_DOCKER_CONTROL_PREFIXES = frozenset({"do", "else", "then"})


_DOCKER_CONTROL_ONLY = frozenset({"done", "fi"})
