# Generated-File Ownership Categories (Website-Migration Taxonomy)

> **Related docs**: [Generated Project Structure](generated_project_structure.md) | [Beta-site migration](../planning/beta-site-migration.md)

**Purpose:** Rules for generated-file ownership during website migration, and the inventory of the `INTENTIONALLY_UNMANAGED` categories carried by `quickscale_devtools/website_migration/`. Existing files in these categories are never structurally replaced or merged; a path may still take part in copy-if-missing adoption or the fresh scaffold's one-time identity reconciliation, neither of which overwrites user-owned contents.

## Rules

**Rule:** The website-migration maintainer tooling
(``quickscale_devtools/website_migration/``) carries a file taxonomy that
classifies every generator-emitted file by its migration path. The taxonomy
combines explicit path tuples with operation-derived directory selectors; a conformance gate
(``test_website_migration_ownership_conformance.py``) derives the expected file
inventory from the template tree (``quickscale_core/generator/templates/``)
and asserts every emitted file is classified.

**Key policy rules:**

1. **``settings/production.py`` is donor-owned; the tool owns rewriting a
   recognized pre-facade database-selection block onto the facade.** The
   fresh-first migration path copies the **donor's**
   ``settings/production.py`` onto the fresh recipient (via
   ``FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES`` and
   ``FRESH_FIRST_DONOR_DJANGO_FILES``).  The donor's production settings carry
   the real deploy-time configuration and must not be replaced by the fresh
   scaffold's defaults.  The effective file must call the versioned
   ``quickscale_core.runtime.settings`` facade.  When the donor file predates
   the facade, the migration rewrites only its inline database/command-selection
   block onto ``resolve_runtime_database_url`` (reusing the donor's canonical
   read names) and carries every other donor setting unchanged, naming the
   rewritten line span and each carried setting in the report; it never asks
   the read-only donor repository to adopt the facade.  Shapes the rewrite does
   not recognize, and rewritten files whose database selection still does not
   resolve through the facade, are refused before any mutation.  Ownership of
   the site customizations therefore stays donor-side, while ownership of the
   database-selection contract moves to the tool, which re-expresses it
   versioned rather than copying it forward.

2. **``start.sh`` and ``predeploy.sh`` follow the recipient scaffold's
   identity.** The fresh scaffold's launchers are the effective launchers and
   are reconciled in place: their embedded slug/package references follow the
   reconciled identity, so the createcachetable env-pair fix and the
   pre-deploy schema split reach the migrated project through the fresh-first
   path. Classified under ``FRESH_FIRST_IDENTITY_ROOT_FILES``; the privileged
   command contract is read from ``predeploy.sh``.

3. **``INTENTIONALLY_UNMANAGED`` is an explicit-only replacement/merge
   ownership class.** Existing files listed there are deliberately outside
   structural replacement and merge paths. A listed path may be created only
   by an explicit copy-if-missing adoption rule, which never overwrites an
   existing user-owned file. The tuple must be empty unless a current template has a
   documented exemption rationale in
   § Inventory below. A
   listed file may also receive fresh-first identity-only reconciliation when
   it contains scaffold-derived slug, package, database-role, or frontend
   package values; that bounded rewrite does not transfer file ownership. No
   implicit fallback — every emitted file must be explicitly accounted for.

4. **The conformance gate fails on unclassified files.**  When a new template
   is added or an existing template is renamed without updating the taxonomy,
   the gate surfaces the gap as a test failure listing every unclassified
   emitted path.  This is the systematic prevention for the class of defect
   where a new or renamed template file is silently missed by the migration
   path (e.g. ``start.sh``/``production.py``).

5. **Every ``INTENTIONALLY_UNMANAGED`` entry carries an explicit category and
   rationale.** No entry may be added without stating why that generated file is
   deliberately outside replacement and merge paths. The inventory itself
   (categories U1–U13, § Inventory) is data the
   conformance gate cross-checks, not policy.

6. **Directory-level classification support.** The conformance gate
   (``_classify_emitted_path``) checks whether any parent directory of an
   emitted path appears in the classified map as a directory entry (path
   ending in ``/``).  This allows grouping many files under a common
   directory without enumerating every path individually. The conflict gate
   derives replacement, merge, and copy-if-missing dispositions from the same
   constants used by the executor. It prevents a path from being both
   structurally replaced/merged and ``INTENTIONALLY_UNMANAGED``; identity-only
   reconciliation and copy-if-missing adoption are the permitted overlaps
   because neither overwrites user-owned contents.

7. **``MODE_REQUIRED_SPECS`` entries are classification sources, not mutation
   authority.**
   The website-migration preflight validation specs
   (``COMMON_REQUIRED_SPECS`` and ``MODE_REQUIRED_SPECS`` in the
   ``quickscale_devtools.website_migration`` package) define files and directories that must exist
   before a migration step can proceed. Some of these specs (notably
   ``frontend/src/App.tsx``) independently appear in an executor-owned
   replacement or merge disposition, but merely being required does not make
   a path structurally managed. The
   conformance test includes all ``MODE_REQUIRED_SPECS`` entries as
   classification sources so that a file like ``frontend/src/App.tsx`` is
   properly categorized as part of the fresh-first required recipient
   surface. The operation-derived disposition model, not this preflight list,
   decides whether overlap with ``INTENTIONALLY_UNMANAGED`` is a conflict.

8. **Fresh-first identity reconciliation covers the complete generated
   identity seam.** The recipient is a throwaway, newly generated scaffold,
   so changing its identity must reconcile every generated occurrence of the
   old slug/package, including derived database role/password values and the
   frontend package name. Reconciliation is field-aware when the source slug
   and package share one token, token-boundary-aware for underscore-bearing
   slugs, and non-cascading. A file can remain user-owned and structurally
   unmanaged while participating in this one-time identity rewrite.

9. **Every structural executor path has an operation-derived disposition.**
   The conformance gate models direct file replacement, directory replacement,
   donor-authoritative merge, and copy-if-missing adoption from the executor's
   constants and selectors. This includes fresh-first component and utility
   directory replacement; a path
   cannot remain ``INTENTIONALLY_UNMANAGED`` merely because the mutation is
   implemented by a directory walk or a dedicated merge helper rather than a
   named copy tuple.

10. **The project-owned design layer is never overwritten.** The
    ``showcase_react`` theme ships ``frontend/design/`` as one folder holding
    the tokens stylesheet, the Tailwind preset, fonts, and brand assets
    (``INTENTIONALLY_UNMANAGED`` directory entry). No QuickScale upgrade or
    ``quickscale apply`` run replaces or merges its files. The website-migration
    tool ports the donor's design into it once (the ``port-donor-design``
    step): every file of a donor that carries its own design layer, or the
    legacy ``frontend/src/index.css`` and ``frontend/tailwind.config.js``
    sources for a donor generated before the layer existed. The React entry
    ``frontend/src/index.css`` imports the layer, and the Django-rendered
    shell resolves the same tokens through that entry, so React and Django
    share one design source.

11. **Project-owned app migrations: model state is regenerated, operations the
    autodetector cannot reproduce are carried.** The fresh-first migration
    drops a donor project-owned app's migration history and regenerates the
    model state with a recipient-local ``makemigrations``.  Non-autodetector
    operations (``RunPython``/``RunSQL``/``SeparateDatabaseAndState`` or a
    custom operation) are never silently dropped: after ``makemigrations``
    succeeds, the tool renders each into an appended recipient migration that
    carries the module-level code the operation references, chained from the
    regenerated terminal migration (which can be a multi-file initial graph).
    It fails closed before any mutation, naming
    the migration, line, and construct, when an operation cannot be carried
    safely — an unresolved module-level reference, no ``Migration`` class
    declaring the operations, a dynamic ``operations`` declaration, or a
    dependency on another app's migration.  The report, the planned action, and
    the handoff prompt name every carried operation.  This is the migration
    tool's answer to the clean-break migration history: the recipient's model
    state is fresh, while migration-owned invariants travel with it.  The tool
    does not statically prove that a carried callback is compatible with the
    regenerated final model state; a callback that depends on state a later
    donor migration removed fails loudly at the recipient's ``migrate`` before
    any deploy, and the named carry inventory is what the handoff review
    checks.

## Inventory

Entries are organized by category. Add new entries to the appropriate category;
add a new category only when the existing ones do not fit, with rationale. Every
generator-emitted file must be explicitly accounted for — the conformance gate
(`test_website_migration_ownership_conformance.py`) derives the expected inventory
from the template tree and fails on any unclassified path.

### Settings files and the runtime facade

``{package}/settings/base.py``, ``production.py``, ``local.py`` and ``modules.py`` are user-owned
and not ``INTENTIONALLY_UNMANAGED``: ``production.py`` is donor-owned (rule 1), the others are
recipient-owned fresh-first requirements. All import their runtime contracts from
``quickscale_core.runtime.settings``.

### Managed theme seam files

``frontend/src/quickscaleSeam.d.ts`` is the theme's managed seam declaration:
it carries the seam's module-key types, rendered from the shipped module set
by ``quickscale apply``/``quickscale update`` under the managed-file hash
guard.  ``frontend/src/quickscaleSeam.keys.ts`` is its generated runtime
companion: the same tables as key arrays, which the theme's seam validator
requires every seam entry against and the theme's tests build their fixtures
from, so the module set has one generated home and a module that joins the set
changes no user-owned theme file.  ``frontend/src/quickscaleSeam.hooks.ts`` is
the managed module-hook file: it renders each active manifest's
``frontend_resources`` declaration — the module's API resource subpaths (a
``{parameter}`` segment becomes a typed builder) and payload types (interfaces
and union aliases) — so a user-owned page imports a resource path, builder, or
response type instead of restating it, and a module release that changes either
changes only this file (SA320).  All three are classified as
recipient-managed protected root files
(``FRESH_FIRST_PROTECTED_ROOT_FILES``): the migration preserves the recipient's
copies and never writes donor content over them, and a project does not
hand-edit the files because the next apply that regenerates the managed files
overwrites them (``quickscale apply --confirm-contract-adoption`` does so
without a configuration change; a plain no-delta apply reports nothing to do).

### Managed CI environment file

``.github/quickscale-ci-env`` is the generated project's managed CI
environment file: it carries each installed module's declared non-live CI
placeholders (the manifest's ``ci_env`` section, keyed by the declaring
option so a renamed ``*_env_var`` follows the project's configuration) as one
``NAME=value`` line per entry.  The generated ``.github/workflows/ci.yml``
stays user-owned and names no module value: it appends this file to GitHub
Actions' ``$GITHUB_ENV`` in one load step, because a workflow has no include
directive.  It is classified as a recipient-managed protected root file
(``FRESH_FIRST_PROTECTED_ROOT_FILES``): the migration preserves the
recipient's copy and never writes donor content over it, and
``quickscale apply``/``quickscale update``/``quickscale remove`` regenerate it
under the managed-file hash guard, so a local edit is reported as drift and a
module release that changes a placeholder changes only this managed file.

### Managed operations page

``quickscale-operations.md`` is the generated project's managed operations
page: it renders each installed module's declared operations text (the
manifest's ``operations`` section) — vendor versions, webhook events, and
endpoints, with the module's declared values, core contract tokens, and
configured options resolved — and the user-owned ``OPERATIONS.md`` links it
once, because Markdown has no include directive.  It is classified as a
recipient-managed protected root file
(``FRESH_FIRST_PROTECTED_ROOT_FILES``): the migration preserves the
recipient's copy and never writes donor content over it, and
``quickscale apply``/``quickscale update``/``quickscale remove`` regenerate it
under the managed-file hash guard, so a local edit is reported as drift and a
module release that changes its operations text changes only this managed
file.

### Managed module regions in user-owned root files

``Makefile``, ``.github/workflows/ci.yml``, and ``docker-compose.yml`` stay
user-owned, but each carries marker-paired managed regions rendered from the
installed modules' manifest ``project_blocks`` declarations:

- ``Makefile``: ``# QuickScale module make targets (managed)`` —
  ``make_targets`` render their names, help text, and recipes, and
  ``make_test_env`` renders ``QUICKSCALE_TEST_ENV``.  The generic
  ``test-backend`` recipe reads that variable, so a module
  that needs a test-only environment value adds it with no core edit.
- ``.github/workflows/ci.yml``: ``# QuickScale module CI environment (managed)``
  inside the test job's ``env``, ``# QuickScale module CI steps (managed)``
  inside its ``steps``, and ``# QuickScale module CI jobs (managed)`` inside
  ``jobs`` — a module declares its own test environment, steps, and jobs.
- ``docker-compose.yml``: ``# QuickScale module environment (managed)``
  inside the backend service's ``environment`` — each ``compose_env`` option
  resolves to the environment-variable name the service passes through from
  the host.

``quickscale apply``, ``quickscale update``, and ``quickscale remove`` refresh
every region from the same manifests, preserving the user-authored lines
around them.  A project generated before the region contract has no markers;
the recorded contract step documents the one-time adoption, and a sync leaves
such a file untouched.  A file carrying only one marker of a pair fails
explicitly instead of leaving a half-written region.

## Categories

### Category U1 — Project-level user-owned files (root-level generated config/docs)
 ``Makefile``, ``README.md``, ``.gitignore``, ``.dockerignore``, ``.editorconfig``,
 ``.pre-commit-config.yaml``,
 ``.env.example``, ``.env``, ``scripts/lint.sh``, ``.github/workflows/ci.yml``,
 ``poetry.lock``, ``db/init.sql``, ``OPERATIONS.md``.
 Rationale: One-time scaffold that the user tailors to their deployment,
 CI, and documentation needs.  ``poetry.lock`` is a dynamically generated
 artifact created by ``_generate_poetry_lock()`` after all templates are
 rendered; it is regenerated by the verification stack (``poetry lock``)
 and is not a structural migration target. Identity-bearing text in the fresh
 scaffold is reconciled in place before handoff; no donor file replaces it.

 **Managed module credential blocks.** ``.env.example`` also carries one managed block per
 enabled credential-bearing module.  ``quickscale apply`` renders each block from that module's
 declared ``*_env_var`` options under the existing ``# QuickScale <Module> (managed)`` /
 ``# End QuickScale <Module>`` markers and never rewrites user-authored lines outside them.
 Enabling ``storage`` or ``backups`` on an existing project therefore adds their credential
 placeholders on the next ``apply`` — a deliberate behavior change for existing projects,
 recorded with the credential-contract derivation.

 **Managed module regions.** The same files also carry the regions described under
 [Managed module regions in user-owned root files](#managed-module-regions-in-user-owned-root-files);
 only the marker-paired region is managed, and the rest of each file remains the user's.

### Category U2 — Package ``__init__`` markers
``{package}/__init__.py``, ``{package}/settings/__init__.py``.
Rationale: These remain recipient-owned package markers. The fresh-first path
renames the package directory and rewrites their generated project-slug
docstrings as an identity-only operation; it does not replace their contents
from the donor.

### Category U3 — Django HTML templates
``templates/404.html``, ``templates/500.html``, ``templates/base.html``,
``templates/index.html``, ``templates/admin/index.html``,
``templates/admin/app_index.html``,
``templates/social/link_tree.html``, ``templates/social/embeds.html``.
Rationale: User-editable Django templates.  Unlike infrastructure files
(``Dockerfile``, ``start.sh``), they are not copy targets during migration.
Fresh-first preserves the recipient's templates structurally while
reconciling generated project-name text; the workflow otherwise does not touch them.
Theme-specific template overrides (social) are
user-owned once generated.  ``templates/components/navigation.html`` is not a
copy target — ``showcase_react`` does not emit a
``templates/components/navigation.html`` template.

 The admin index templates render a module-owned
 ``templates/admin/<app_label>/quickscale_shortcut.html`` through the generic
 ``quickscale_admin`` runtime tag, so the user-owned template itself names no
 module and a module adds or changes its shortcut in its own package.

### Category U4 — Static assets
``frontend/public/favicon.svg``.
Rationale: User-owned static file.  Generated once; not a migration target.
``static/css/style.css`` and ``static/images/favicon.svg`` are not copy
targets — ``showcase_react`` does not emit them.

### Category U5 — Test scaffolding
``tests/__init__.py``, ``tests/conftest.py``, ``tests/test_example.py``,
``tests/test_tenant_isolation.py``.
Rationale: One-time generated test scaffold that users customize. Fresh-first
reconciles only its generated project-name docstrings.

### Category U6 — Frontend build settings (user-owned after generation)
``frontend/vite.config.ts``, ``frontend/tsconfig.json``,
``frontend/eslint.config.js``, ``frontend/postcss.config.js``,
``frontend/pnpm-workspace.yaml``, ``frontend/pnpm-lock.yaml``,
``frontend/.prettierignore``, ``frontend/.prettierrc``,
``frontend/vitest.config.ts``, ``frontend/playwright.config.ts``,
``frontend/components.json``, ``frontend/tailwind.config.js``,
``frontend/index.html``.
Rationale: Generated once, user-editable, and not migration targets — the
workflow keeps the recipient's copies exactly as generated. The generated
``frontend/pnpm-lock.yaml`` pins the image build's frontend dependencies; the
project refreshes it with its own ``pnpm install`` and the image fails closed
without it. ``frontend/package.json``
is not in this category: it is part of the fresh-first identity seam and is
classified through ``FRESH_FIRST_IDENTITY_ROOT_FILES`` instead.

### Category U7 — Frontend user-owned source files
 ``frontend/src/main.tsx``, ``frontend/src/renderQuickScaleRoot.tsx``,
 ``frontend/src/index.css``,
 ``frontend/src/vite-env.d.ts``, ``frontend/src/posthog-js.d.ts``,
 ``frontend/src/lib/utils.ts``, ``frontend/src/lib/analytics.ts``,
 ``frontend/src/lib/csrf.ts``, ``frontend/src/lib/validateQuickScaleSeam.ts``,
  ``frontend/src/test/setup.ts``,
  ``frontend/src/test/seamFixtures.ts``,
  ``frontend/src/test/App.test.tsx``,
  ``frontend/src/test/AppRoutes.test.tsx``,
  ``frontend/src/test/analytics.test.ts``,
  ``frontend/src/test/csrf.test.tsx``,
  ``frontend/src/test/FormRenderer.test.tsx``,
  ``frontend/src/test/formFields.test.tsx``,
  ``frontend/src/test/layoutComponents.test.tsx``,
  ``frontend/src/test/orgComponents.test.tsx``,
  ``frontend/src/test/orgListPage.test.tsx``,
  ``frontend/src/test/RootDispatch.test.tsx``,
  ``frontend/src/test/PublicSocialPages.test.tsx``,
  ``frontend/src/test/settingsPage.test.tsx``,
  ``frontend/src/test/socialLinkTreeStates.test.tsx``,
  ``frontend/src/test/themeStore.test.ts``,
  ``frontend/src/test/uiPrimitives.test.tsx``,
  ``frontend/src/test/useApiErrors.test.ts``,
  ``frontend/src/test/useModules.test.tsx``,
  ``frontend/src/test/useOrgNavigation.test.tsx``,
  ``frontend/src/test/useOrgs.test.tsx``,
  ``frontend/src/test/validateQuickScaleSeam.test.ts``,
  ``frontend/src/test/viteAssetRouting.test.ts``,
 ``frontend/e2e/home.spec.ts``.
 Rationale: User-editable application source, styles, type declarations,
 utility helpers, and test files. They are not structural migration targets;
 generated identity text in ``frontend/e2e/home.spec.ts`` is reconciled on the
 fresh scaffold. ``frontend/src/hooks/useModules.ts`` is identity-reconciled on
 the fresh scaffold, and
 ``frontend/src/App.tsx`` is classified by the fresh-first
 required recipient spec (``MODE_REQUIRED_SPECS``) — it is a required
 preflight check for the fresh-first path and is copied from donor to
 recipient during the copy-custom-router-and-pages step (see rule 7).
 Existing page files stay with the user; donor-only pages may be adopted through
 the explicit copy-if-missing path. ``frontend/src/stores/`` is not in this
 category because fresh-first replaces donor utility directories structurally.

### Category U8 — shadcn/ui components
All ``frontend/src/components/ui/*.tsx`` files.
Rationale: shadcn/ui components are copy-pasted user-owned code after
generation.  They are not migration targets.

### Fresh-first component directories — structurally replaced
Generated files below ``frontend/src/components/`` are not intentionally
unmanaged unless their first directory is ``ui/``. Fresh-first replaces each
donor component directory except ``ui/`` as one structural operation. This
includes generated ``forms/``, ``layout/``, ``orgs/``, and ``social/`` files;
the operation-derived conformance classifier covers the directory walk so these
paths cannot silently re-enter ``INTENTIONALLY_UNMANAGED``.

### Category U9 — Non-module pages
``frontend/src/pages/Dashboard.tsx``, ``frontend/src/pages/NotFound.tsx``,
``frontend/src/pages/ProfilePage.tsx``, ``frontend/src/pages/SettingsPage.tsx``.
Rationale: User-editable application pages, always emitted for the
React theme.  Fresh-first copies donor-only pages via the hardcoded
copy-custom-router-and-pages step, but individual pages are not
migration-managed taxonomy entries.

### Category U10 — Module-owned pages (non-module-surface)
``frontend/src/pages/BlogPage.tsx``, ``frontend/src/pages/CrmPage.tsx``,
``frontend/src/pages/ListingsPage.tsx``, ``frontend/src/pages/FormsPage.tsx``,
``frontend/src/pages/SocialLinkTreePublicPage.tsx``,
``frontend/src/pages/SocialEmbedsPublicPage.tsx``.
Rationale: All six pages are emitted unconditionally as dormant entries and
gated at runtime by the installed-module flags (SA105); the gating module
decides whether their routes render, never whether the file exists.  After
generation they are user-editable and are not structurally managed; donor-only
copies may still be adopted through the explicit copy-if-missing walk, which
never overwrites an existing user file.

### Category U11 — Org pages (React theme)
``frontend/src/pages/orgs/OrgLayout.tsx``,
``frontend/src/pages/orgs/OrgDashboardPage.tsx``,
``frontend/src/pages/orgs/OrgMembersPage.tsx``,
``frontend/src/pages/orgs/OrgSettingsPage.tsx``,
``frontend/src/pages/orgs/OrgCreatePage.tsx``,
``frontend/src/pages/orgs/OrgListPage.tsx``.
Rationale: Generated org-management pages that are user-editable after
generation.  Not migration targets.

### Category U12 — Non-infrastructure hooks
``frontend/src/hooks/useOrgNavigation.ts``,
``frontend/src/hooks/useOrgs.ts``,
``frontend/src/hooks/useApi.ts``,
``frontend/src/hooks/useFormSchema.ts``.
Rationale: User-editable React hooks.  ``useModules.ts`` is
identity-reconciled on the fresh scaffold; the rest, including
``usePublicSocialSurface.ts``, are user-owned after generation.

### Category U13 — Project-owned design layer (never overwritten)
``frontend/design/`` — the directory entry covers every file the layer ships or
later holds: ``tokens.css`` (the design-token stylesheet and Tailwind entry the
React host imports), ``tailwind.preset.js`` (consumed by
``frontend/tailwind.config.js`` through ``presets``), ``fonts/`` (project-owned
webfonts), and ``brand/`` (project-owned brand assets imported by components or
the stylesheet).
Rationale: One folder the project owns outright. No QuickScale upgrade or
``quickscale apply`` run replaces or merges its files; the website-migration tool
copies the donor's design into it once during migration (SA214 slice d), and
every edit afterwards belongs to the project. ``frontend/src/index.css``
remains the React entry that imports the layer, and the Django-rendered shell
resolves the same tokens through that entry (or its production build). The
served favicon stays at ``frontend/public/favicon.svg`` instead of moving into
``brand/`` so the generated ``{% static 'frontend/favicon.svg' %}`` links keep
working.

### Category U6/U7 update (design consumer files)
``frontend/tailwind.config.js`` (U6) and ``frontend/src/index.css`` (U7) stay
user-owned, but since SA214 slice (d) they are also the design layer's
consumers: the config consumes ``design/tailwind.preset.js`` and the entry
imports ``design/tokens.css``. They remain non-migration targets; the layer
above is where design values live.
