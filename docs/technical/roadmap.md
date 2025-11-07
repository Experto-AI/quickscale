# QuickScale Development Roadmap

## General Introduction

**Purpose:** This document outlines the development timeline, implementation phases, and specific tasks for building QuickScale.

**Content Guidelines:**
- Organize tasks by phases with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New development phases and milestone planning
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

**What NOT to Add Here:**
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

## Broad Overview of the Roadmap

QuickScale follows an evolution-aligned roadmap that starts as a personal toolkit and potentially evolves into a community platform based on real usage and demand.

**Evolution Strategy:** Personal toolkit first, community platform later. See [quickscale.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first).


**Roadmap Phases:**

1. **Phase 1: Foundation + Core Modules (Showcase HTML Theme Only)**
   - Theme system infrastructure and split branch management
   - Core modules: auth, blog, billing, teams
   - Showcase architecture for module discovery

2. **Phase 2: Additional Themes (Port Existing Modules)**
   - HTMX theme with Alpine.js
   - React theme with TypeScript SPA
   - Port all core modules to new themes

3. **Phase 3: Expand Features (All Themes)**
   - Notifications module with email infrastructure
   - Advanced module management features
   - Workflow validation and real-world testing

4. **Phase 4: Community Platform (Optional v1.0.0+)**
   - PyPI package distribution
   - Theme package system
   - Marketplace and community features

**Key Milestones:**
- **v0.69.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

### Module Configuration Strategy (v0.65.0+)

### Overview
Modules require configuration when embedded (e.g., auth signup enabled/disabled, billing plan defaults). QuickScale uses a **two-phase approach** for module configuration:

- **Phase 1 (MVP: v0.65.0-v0.69.0)**: Interactive prompts during `embed` command
- **Phase 2 (Post-MVP: v1.0.0+)**: Optional YAML configuration file support

This balances MVP simplicity (no YAML overhead) with good UX (not forcing manual settings editing).

### Phase 1: Interactive Embed Configuration (MVP, v0.65.0+)

**When**: Immediately, starting with v0.65.0 auth module

**How it works**:
```bash
$ quickscale embed --module auth
📦 Embedding auth module from splits/auth-module...

# Interactive prompts based on module requirements
? Enable user registration? (y/n) [y]: y
? Email verification required? (y/n) [n]: n
? Custom User model fields? (y/n) [n]: n

✅ Module 'auth' embedded successfully!

Automatic changes made:
  ✅ Added 'modules.auth' to INSTALLED_APPS
  ✅ Added allauth configuration to settings
  ✅ Added auth URLs to urls.py
  ✅ Created initial migration

Next steps:
  1. Review module code in modules/auth/
  2. Run migrations: python manage.py migrate
  3. Visit http://localhost:8000/accounts/login
```

**Benefits**:
- ✅ No manual settings editing required
- ✅ All configuration choices documented automatically
- ✅ Works for 2-3 modules without feeling tedious
- ✅ MVP-aligned (no YAML complexity)
- ✅ Clear, self-documenting UX

**Scalability**: Works well up to ~3-5 modules. Beyond that, YAML becomes valuable (Post-MVP).

### Phase 2: YAML Configuration (Post-MVP, v1.0.0+)

**When**: After 5+ modules with complex interactions; optional convenience feature

**Why defer to Post-MVP**:
- 📋 MVP focuses on core 3 modules (auth, billing, teams) — interactive prompts work fine
- 🎯 Complexity threshold not reached until v0.70.0+ with multiple themes
- 🚀 Faster to ship MVP with simple interactive UX than build YAML system
- 🔄 Interactive approach creates foundation for YAML (same config options)

**Future workflow** (v1.0.0 example):
```yaml
# quickscale.yml (v1.0.0+)
version: 0.66.0
project_name: "myapp"
theme: "showcase_react"

# One-time init with config file
modules:
  auth:
    enabled: true
    config:
      ACCOUNT_ALLOW_REGISTRATION: true
      ACCOUNT_EMAIL_VERIFICATION: "optional"

  billing:
    enabled: true
    config:
      STRIPE_API_KEY: "${STRIPE_API_KEY}"  # From .env
      BILLING_CURRENCY: "usd"

# Usage: quickscale init myproject --config quickscale.yml
```

**Then**: Existing `embed` command still works interactively for adding modules post-init.

### Implementation Notes for Module Developers

**In v0.65.0+, when creating a module's embed handler**:

1. **Define configuration options** as a list of click.confirm/click.prompt questions
2. **Store configuration state** in `.quickscale/config.yml` (module tracking)
3. **Apply configuration** to:
   - `INSTALLED_APPS` (add module)
   - `settings/*.py` (module-specific settings)
   - `urls.py` (include module URLs)
   - Django migrations (run initial migration)
4. **Document all options** in module README.md
5. **Make defaults sensible** (e.g., "Allow registration? [y]" defaults to yes)

**Example: Auth module v0.65.0 configuration**
```python
# quickscale_cli/commands/module_commands.py (auth-specific logic)

def embed_auth_module(remote: str) -> None:
    # Interactive prompts
    allow_signup = click.confirm("Enable user registration?", default=True)
    email_verification = click.confirm("Email verification required?", default=False)

    # Apply configuration
    # ... (settings updates, INSTALLED_APPS, etc.)
```

- 📄 [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture)
- 📄 [decisions.md: MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative) — YAML explicitly OUT (Post-MVP)
- 📄 [scaffolding.md: Post-MVP YAML Config](./scaffolding.md#post-mvp-structure)

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Previous Releases:** [release notes](./releases.md).
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

**Current Status:** v0.65.0 (Released November 1, 2025) — Authentication module delivered.
**Next Release:** v0.66.0 - Wagtail Blog Module (`quickscale_modules.blog`)



## Roadmap Releases

### Current State Assessment
- ✅ **Current Version**: v0.65.0 (Released November 1, 2025) — Authentication delivered (basic django-allauth integration; email delivery/setup not included). Development tooling and template improvements shipped alongside the auth work.
- 🔄 **Next Release**: v0.66.0 - Wagtail Blog Module (`quickscale_modules.blog`) — Wagtail-based company site + blog (module-first). **Status**: Planned and prioritized as the immediate next task (module scaffold pending).

### Showcase HTML Theme: Module Showcase Architecture

**Strategic Decision (v0.65.0+)**: The Showcase HTML theme serves as a **living showcase** for all QuickScale modules, demonstrating capabilities whether modules are installed or not.

**Rationale**:
- **Marketing**: New users see what QuickScale offers immediately
- **Educational**: Clear demonstrations of each module's features
- **Composability**: Visual proof of QuickScale's modular architecture
- **Discovery**: Users understand what modules to install next

**Implementation Requirements** (All Module Releases):

Every module release (v0.65.0+) MUST include:

1. **Showcase Landing Page Updates**: Add module card to `index.html` with:
   - Module name, description, and key features
   - Installation status indicator (installed vs available)
   - "Try Demo" link (works whether installed or not)
   - "Install Module" instructions if not installed

2. **Demo/Preview Pages**: Create static preview pages that work WITHOUT module installed:
   - Show UI mockups/screenshots of module features
   - Explain what the module does
   - Link to installation instructions
   - When module IS installed, link to actual functional pages

3. **Navigation Integration**: Update base template navigation to include:
   - "Modules" dropdown showing all available modules
   - Visual indicators for installed vs available
   - Links to demos/actual pages based on installation status

**Landing Page Structure** (`index.html`):
```html
<section class="hero">
  <h1>Welcome to {{ project_name }}</h1>
  <p>Built with QuickScale - Compose your Django SaaS</p>
</section>

<section class="modules-showcase">
  <h2>Available Modules</h2>

  <!-- Auth Module Card -->
  <div class="module-card installed">
    <h3>🔐 Authentication</h3>
    <p>User authentication with django-allauth</p>
    <ul class="features">
      <li>Email/password login</li>
      <li>Password reset flows</li>
      <li>Profile management</li>
    </ul>
    <a href="/auth/demo/" class="btn-demo">View Features</a>
    <span class="status installed">✓ Installed</span>
  </div>

  <!-- Billing Module Card (example when NOT installed) -->
  <div class="module-card available">
    <h3>💳 Billing & Subscriptions</h3>
    <p>Stripe integration with subscription management</p>
    <ul class="features">
      <li>Multiple pricing tiers</li>
      <li>Usage tracking</li>
      <li>Invoice management</li>
    </ul>
    <a href="/billing/preview/" class="btn-demo">Preview Features</a>
    <span class="status available">Install with: quickscale embed --module billing</span>
  </div>

  <!-- More module cards... -->
</section>
```

**Template Detection Pattern**:
```django
{% load static %}

{# Check if module is installed #}
{% if 'modules.auth' in settings.INSTALLED_APPS %}
  <a href="{% url 'auth:login' %}">Go to Login</a>
{% else %}
  <a href="{% url 'auth_preview' %}">Preview Auth Features</a>
  <p class="install-hint">Install: <code>quickscale embed --module auth</code></p>
{% endif %}
```

---

## Module Showcase Implementation Guide (All Modules v0.65.0+)

**MANDATORY REQUIREMENTS**: Every module release MUST update the Showcase HTML theme showcase. This section defines the standard pattern.

### 1. Module Card Specification

Each module MUST have a card in `themes/showcase_html/templates/index.html.j2`:

```html
<div class="module-card {% if module_installed %}installed{% else %}available{% endif %}">
  <!-- Icon + Name -->
  <h3>{{ module_icon }} {{ module_name }}</h3>

  <!-- One-liner description -->
  <p class="module-description">{{ short_description }}</p>

  <!-- 3-5 key features -->
  <ul class="features">
    <li>{{ feature_1 }}</li>
    <li>{{ feature_2 }}</li>
    <li>{{ feature_3 }}</li>
  </ul>

  <!-- Action button -->
  <a href="{{ demo_or_functional_url }}" class="btn-demo">
    {% if module_installed %}View Features{% else %}Preview Demo{% endif %}
  </a>

  <!-- Status indicator -->
  <span class="status {% if module_installed %}installed{% else %}available{% endif %}">
    {% if module_installed %}
      ✓ Installed
    {% else %}
      Install with: <code>quickscale embed --module {{ module_slug }}</code>
    {% endif %}
  </span>
</div>
```

**Required Fields per Module**:
- `module_icon`: Single emoji representing the module (🔐 for auth, 💳 for billing, 👥 for teams)
- `module_name`: Display name (e.g., "Authentication", "Billing & Subscriptions")
- `short_description`: One-line value proposition (max 80 chars)
- `features`: 3-5 bullet points of key capabilities
- `demo_or_functional_url`: `/auth/demo/` if installed, `/auth/preview/` if not
- `module_slug`: CLI slug for embedding (e.g., "auth", "billing", "teams")

### 2. Preview Page Specification

Each module MUST create a preview page template: `themes/showcase_html/templates/{module}_preview.html.j2`

**Structure**:
```html
{%raw%}{% extends "base.html" %}
{% block title %}{{ module_name }} - Preview{% endblock %}

{% block content %}
<div class="preview-container">
  <!-- Header -->
  <header class="preview-header">
    <h1>{{ module_icon }} {{ module_name }}</h1>
    <p class="tagline">{{ expanded_description }}</p>
  </header>

  <!-- Installation Status Check -->
  {% if module_installed %}
    <div class="alert success">
      ✓ This module is installed. <a href="{{ functional_url }}">Go to {{ module_name }}</a>
    </div>
  {% else %}
    <div class="alert info">
      This is a preview. Install with: <code>quickscale embed --module {{ module_slug }}</code>
    </div>
  {% endif %}

  <!-- Feature Showcases (2-4 sections) -->
  <section class="feature-showcase">
    <h2>{{ feature_1_title }}</h2>
    <div class="feature-demo">
      <!-- Screenshot, mockup, or description -->
      <img src="{% static 'images/previews/{{ module_slug }}_{{ feature_1_slug }}.png' %}" alt="{{ feature_1_title }}">
      <p>{{ feature_1_description }}</p>
    </div>
  </section>

  <!-- Repeat for features 2-4 -->

  <!-- Installation Instructions -->
  <section class="installation">
    <h2>Installation</h2>
    <ol>
      <li>Run: <code>quickscale embed --module {{ module_slug }}</code></li>
      <li>Answer configuration prompts</li>
      <li>Restart your development server</li>
      <li>Visit <code>{{ functional_url }}</code></li>
    </ol>
  </section>

  <!-- Documentation Link -->
  <footer class="preview-footer">
    <a href="{{ module_docs_url }}" class="btn">View Full Documentation</a>
  </footer>
</div>
{% endblock %}{%endraw%}
```

### 3. Context Processor for Module Detection

**File**: `quickscale_core/src/quickscale_core/context_processors.py` (create if not exists)

```python
"""Context processors for QuickScale themes."""

from django.conf import settings
from typing import Dict, Any


def installed_modules(request) -> Dict[str, Any]:
    """Provide module installation status to all templates."""
    installed_apps = settings.INSTALLED_APPS

    return {
        'modules': {
            'auth': 'modules.auth' in installed_apps,
            'billing': 'modules.billing' in installed_apps,
            'teams': 'modules.teams' in installed_apps,
            'notifications': 'modules.notifications' in installed_apps,
        },
        'quickscale_version': getattr(settings, 'QUICKSCALE_VERSION', 'unknown'),
    }
```

**Register in generated project's settings**:
```python
TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                # ... default processors
                'quickscale_core.context_processors.installed_modules',
            ],
        },
    },
]
```

### 4. CSS Styles for Showcase (Required Additions)

**File**: `themes/showcase_html/static/css/style.css.j2` (append these styles)

```css
/* Module Showcase Styles */
.modules-showcase {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
  margin: 3rem 0;
}

.module-card {
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  padding: 1.5rem;
  transition: all 0.3s ease;
}

.module-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.module-card.installed {
  border-color: #10b981;
  background: #f0fdf4;
}

.module-card h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
}

.module-card .module-description {
  color: #6b7280;
  margin: 0.5rem 0 1rem 0;
}

.module-card .features {
  list-style: none;
  padding: 0;
  margin: 1rem 0;
}

.module-card .features li {
  padding: 0.25rem 0;
  padding-left: 1.5rem;
  position: relative;
}

.module-card .features li:before {
  content: "✓";
  position: absolute;
  left: 0;
  color: #10b981;
}

.module-card .btn-demo {
  display: inline-block;
  background: #3b82f6;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
  margin-top: 1rem;
}

.module-card .btn-demo:hover {
  background: #2563eb;
}

.module-card .status {
  display: block;
  margin-top: 1rem;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 0.875rem;
}

.module-card .status.installed {
  background: #d1fae5;
  color: #065f46;
}

.module-card .status.available {
  background: #dbeafe;
  color: #1e40af;
}

/* Preview Page Styles */
.preview-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
}

.preview-header {
  text-align: center;
  margin-bottom: 3rem;
}

.preview-header h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.preview-header .tagline {
  font-size: 1.25rem;
  color: #6b7280;
}

.alert {
  padding: 1rem;
  border-radius: 4px;
  margin: 2rem 0;
}

.alert.success {
  background: #d1fae5;
  border: 1px solid #10b981;
  color: #065f46;
}

.alert.info {
  background: #dbeafe;
  border: 1px solid #3b82f6;
  color: #1e40af;
}

.feature-showcase {
  margin: 3rem 0;
}

.feature-showcase h2 {
  margin-bottom: 1rem;
}

.feature-demo img {
  width: 100%;
  border-radius: 8px;
  margin-bottom: 1rem;
  border: 1px solid #e5e7eb;
}

.installation {
  background: #f9fafb;
  padding: 2rem;
  border-radius: 8px;
  margin: 3rem 0;
}

.installation ol {
  margin-left: 1.5rem;
}

.installation code {
  background: #fff;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-family: monospace;
  border: 1px solid #e5e7eb;
}

.preview-footer {
  text-align: center;
  margin-top: 3rem;
}

.preview-footer .btn {
  display: inline-block;
  background: #3b82f6;
  color: white;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  text-decoration: none;
  font-weight: 600;
}

.preview-footer .btn:hover {
  background: #2563eb;
}
```

### 5. Module Release Checklist (Showcase Updates)

When releasing a new module, complete these showcase tasks:

- [ ] **Add module card** to `themes/showcase_html/templates/index.html.j2`:
  - [ ] Choose appropriate emoji icon
  - [ ] Write compelling one-liner description
  - [ ] List 3-5 key features
  - [ ] Configure demo/preview URL
  - [ ] Add installation command
- [ ] **Create preview page** `themes/showcase_html/templates/{module}_preview.html.j2`:
  - [ ] Write expanded module description
  - [ ] Create 2-4 feature showcase sections
  - [ ] Add mockup images or descriptions
  - [ ] Include installation instructions
  - [ ] Link to module documentation
- [ ] **Update context processor** in `quickscale_core/context_processors.py`:
  - [ ] Add module slug to `installed_modules()` dict
- [ ] **Add preview route** to generated project's `urls.py` template:
  - [ ] Create view returning preview page
  - [ ] URL pattern: `/{module}/preview/`
- [ ] **Test showcase**:
  - [ ] Generate new project without module
  - [ ] Verify module card shows "Available" status
  - [ ] Verify preview page loads correctly
  - [ ] Embed module via CLI
  - [ ] Verify module card updates to "Installed"
  - [ ] Verify links now point to functional pages
- [ ] **Screenshot/mockups** (if applicable):
  - [ ] Create mockup images for key features
  - [ ] Save to `themes/showcase_html/static/images/previews/`
  - [ ] Optimize images (compress, appropriate size)

### 6. Module-Specific Examples

**Auth Module (v0.65.0)**:
- Icon: 🔐
- Name: Authentication
- Description: "User authentication with django-allauth"
- Features: Email/password login, Password reset flows, Profile management
- Preview URL: `/auth/preview/`
- Functional URL: `/accounts/login/` (when installed)

**Billing Module (v0.68.0)**:
- Icon: 💳
- Name: Billing & Subscriptions
- Description: "Stripe integration with subscription management"
- Features: Multiple pricing tiers, Usage tracking, Invoice management, Webhook handling
- Preview URL: `/billing/preview/`
- Functional URL: `/billing/plans/` (when installed)

**Teams Module (v0.69.0)**:
- Icon: 👥
- Name: Teams & Multi-tenancy
- Description: "Collaborative workspaces with role-based permissions"
- Features: Team creation, Member invitations, Role management, Row-level security
- Preview URL: `/teams/preview/`
- Functional URL: `/teams/` (when installed)

---

### v0.64.0: Theme Rename (`starter_html` → `showcase_html`)
**: Theme Rename — Atomic rename from `starter_*` to `showcase_*`. See `docs/releases/release-v0.64.0-implementation.md` for details and migration notes.

---
---

**: Authentication Module (basic) & Development Tooling — Delivered a django-allauth-based authentication integration and a set of development/tooling and template improvements. NOTE: email sending/delivery configuration was intentionally left out of the initial auth delivery and remains a follow-up task. See `docs/releases/release-v0.65.0-implementation.md` for implementation notes (if present) or the release plan document.

**Note**: The originally planned "Showcase Architecture" work (module cards, preview pages) has been deferred to v0.67.0 to prioritize critical auth module fixes and development tooling improvements.

---

### v0.67.0: Showcase Architecture - Module Discovery & Preview System

**Objective**: Transform the Showcase HTML theme into a living demonstration platform for all QuickScale modules. Establish the showcase pattern that all future modules will follow.

**Timeline**: After v0.66.0
**Status**: Planned - Deferred from v0.65.0 to prioritize auth fixes

**Scope Boundaries**:
- ✅ **IN**: Showcase landing page (`index.html.j2`) with module cards
- ✅ **IN**: Auth preview page (`auth_preview.html.j2`) with feature demonstrations
- ✅ **IN**: Placeholder cards for billing, teams, notifications (marked "Coming Soon")
- ✅ **IN**: Module detection context processor enhancements
- ✅ **IN**: Showcase CSS styles (responsive grid, status badges)
- ✅ **IN**: Preview page URL routing for all modules
- ✅ **IN**: Minimum 70% test coverage for new components
- ❌ **OUT**: New modules (billing/teams remain v0.68.0+)

**Implementation Tasks**: See detailed plan in `docs/releases/release-v0.65.0-plan.md` (original scope for v0.65.0).

---

### v0.68.0: `quickscale_modules.billing` - Billing Module

**Objective**: Create reusable billing module wrapping dj-stripe for Stripe subscriptions, plans, pricing tiers, webhook handling, and invoice management. Showcase HTML theme only. **INCLUDES**: Showcase integration for billing features.

**Timeline**: After v0.67.0 (showcase architecture)

**Status**: Planned - Billing module implementation

**Scope**: See [Module Creation Guide](#module-creation-guide-for-v05x0-releases) and [competitive_analysis.md Billing Requirements](../overview/competitive_analysis.md#4-stripe-integration--subscription-management).

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

**Required Showcase Updates** (MANDATORY for this release):
- [ ] Add billing module card to `index.html.j2` with:
  - [ ] Module description: "Stripe integration with subscription management"
  - [ ] Key features: Multiple pricing tiers, usage tracking, invoice management, webhook handling
  - [ ] Demo link to billing preview page
  - [ ] Installation status indicator
- [ ] Create `billing_preview.html.j2` template showing:
  - [ ] Pricing page mockup (Free, Pro, Enterprise tiers example)
  - [ ] Subscription management dashboard mockup
  - [ ] Invoice history mockup
  - [ ] Installation instructions if not installed
- [ ] Update `style.css.j2` for billing-specific showcase styles (if needed)
- [ ] Update navigation menu to include billing demo link

---

### v0.69.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

**Objective**: Create reusable teams module with multi-tenancy patterns, role-based permissions, invitation system, and row-level security. Showcase HTML theme only. **INCLUDES**: Showcase integration for teams features.

**Timeline**: After v0.68.0 (billing)

**Status**: 🎯 **SAAS FEATURE PARITY MILESTONE** - At this point QuickScale matches SaaS Pegasus on core features (auth, billing, teams).

**Scope**: See [Module Creation Guide](#module-creation-guide-for-v05x0-releases) and [competitive_analysis.md Teams Requirements](../overview/competitive_analysis.md#6-teammulti-tenancy-pattern).

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

**Required Showcase Updates** (MANDATORY for this release):
- [ ] Add teams module card to `index.html.j2` with:
  - [ ] Module description: "Multi-tenancy with team collaboration"
  - [ ] Key features: Role-based permissions, team invitations, row-level security, member management
  - [ ] Demo link to teams preview page
  - [ ] Installation status indicator
- [ ] Create `teams_preview.html.j2` template showing:
  - [ ] Team dashboard mockup (team list, member count)
  - [ ] Invitation flow mockup (send/accept invitations)
  - [ ] Role management mockup (Owner, Admin, Member permissions)
  - [ ] Installation instructions if not installed
- [ ] Update `style.css.j2` for teams-specific showcase styles (if needed)
- [ ] Update navigation menu to include teams demo link
- [ ] **Showcase now complete**: All 3 core modules (auth, billing, teams) have showcase cards

---

### v0.70.0: HTMX Frontend Theme

**Objective**: Create HTMX + Alpine.js theme variant and port existing modules (auth, billing, teams) to this theme. **INCLUDES**: Module showcase for HTMX theme.

**Timeline**: After v0.69.0 (teams)

**Status**: Planned - Second theme variant for server-rendered, low-JS applications

**Scope**:
- Create `themes/showcase_htmx/` directory structure
- HTMX + Alpine.js base templates
- **Create module showcase landing page** (HTMX version with dynamic loading)
- Port auth module components (login, signup, account management)
- Port billing module components (subscription management, pricing pages)
- Port teams module components (team dashboard, invitations, roles)
- **Create preview pages for all 3 modules** (HTMX-enhanced)
- Tailwind CSS or similar modern CSS framework
- Progressive enhancement patterns

**Showcase Requirements** (HTMX Theme):
- [ ] Create `index.html.j2` for HTMX theme with module showcase
- [ ] Use HTMX for dynamic module card loading (show installed vs available)
- [ ] Create `auth_preview.html.j2`, `billing_preview.html.j2`, `teams_preview.html.j2` with HTMX interactions
- [ ] Add Alpine.js for client-side interactivity (collapsible sections, tabs)
- [ ] Reuse module detection context processor from HTML theme

**Success Criteria**:
 - `quickscale init myproject --theme showcase_htmx` generates HTMX-based project
- All existing modules (auth/billing/teams) work with HTMX theme
- Backend code remains unchanged (100% theme-agnostic)
- Documentation includes HTMX theme examples

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### v0.71.0: React Frontend Theme

**Objective**: Create React + TypeScript SPA theme variant and port existing modules (auth, billing, teams) to this theme. **INCLUDES**: Module showcase for React theme.

**Timeline**: After v0.70.0 (HTMX theme)

**Status**: Planned - Third theme variant for modern SPA applications

**Scope**:
- Create `themes/showcase_react/` directory structure
- React + TypeScript + Vite base setup
- **Create module showcase landing page** (React SPA with routing)
- Django REST Framework API endpoints for auth/billing/teams
- Port auth module components (login, signup, account management)
- Port billing module components (subscription management, pricing pages)
- Port teams module components (team dashboard, invitations, roles)
- **Create preview pages for all 3 modules** (React components)
- Modern component library (Shadcn/UI or similar)
- State management (React Query, Zustand, or similar)

**Showcase Requirements** (React Theme):
- [ ] Create `App.tsx` with module showcase landing page
- [ ] Use React Router for navigation (/, /auth/preview, /billing/preview, /teams/preview)
- [ ] Create reusable `ModuleCard` component showing installation status
- [ ] Create `AuthPreview.tsx`, `BillingPreview.tsx`, `TeamsPreview.tsx` components
- [ ] Add API endpoint to check module installation status (`/api/modules/status/`)
- [ ] Use React Query for fetching module status
- [ ] Responsive design with Tailwind CSS or similar

**Success Criteria**:
- `quickscale init myproject --theme showcase_react` generates React SPA project
- Module showcase works dynamically (shows installed vs available modules)
- All existing modules (auth/billing/teams) work with React theme
- Backend code remains unchanged (100% theme-agnostic)
- API endpoints auto-generated or clearly documented
- Documentation includes React theme examples

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### v0.72.0: `quickscale_modules.notifications` - Notifications Module

**Objective**: Create reusable notifications module wrapping django-anymail for multiple email backends, transactional templates, and async email via Celery. All 3 themes supported (Showcase HTML, HTMX, React).

**Timeline**: After v0.70.0 (React theme)

**Status**: Detailed implementation plan to be created before starting work.

**Scope**: See [Module Creation Guide](#module-creation-guide-for-v05x0-releases) and [competitive_analysis.md Email Requirements](../overview/competitive_analysis.md#8-email-infrastructure--templates).

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### v0.73.0: Advanced Module Management Features

**Objective**: Enhance module management with batch operations and advanced features.

**Timeline**: After v0.72.0 (notifications)

**Rationale**: Basic embed/update/push commands implemented in v0.62.0. This release adds convenience features based on real usage patterns.

**Scope**:
- Batch operations: `quickscale update --all` (update all installed modules)
- Status command: `quickscale status` (show installed modules and versions)
- Module discovery: `quickscale list-modules` (show available modules)
- Enhanced conflict resolution workflows
- Improved diff previews and change summaries

**Success Criteria**:
- Batch updates work safely across multiple modules
- Clear status overview of module versions
- Easy discovery of new available modules
- Better UX for handling merge conflicts

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

#### **Technical Implementation Notes (v0.62.0 Split Branch Foundation)**

**1. Split Branch Architecture**:

QuickScale monorepo maintains split branches for each module:
```
Branches:
├── main                       # All development happens here
├── splits/auth-module         # Auto-generated from quickscale_modules/auth/
├── splits/billing-module      # Auto-generated from quickscale_modules/billing/
└── splits/teams-module        # Auto-generated from quickscale_modules/teams/
```

**2. GitHub Actions Auto-Split Workflow**:

```yaml
# .github/workflows/split-modules.yml
name: Split Module Branches
on:
  push:
    tags:
      - 'v*'

jobs:
  split:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for split

      - name: Split auth module
        run: |
          git subtree split --prefix=quickscale_modules/auth -b splits/auth-module --rejoin
          git push origin splits/auth-module

      - name: Split billing module
        run: |
          git subtree split --prefix=quickscale_modules/billing -b splits/billing-module --rejoin
          git push origin splits/billing-module
```

**3. Module Configuration Tracking**:

Created in user's project at `.quickscale/config.yml`:
```yaml
# QuickScale module configuration
default_remote: https://github.com/<org>/quickscale.git

# Installed modules
modules:
  auth:
    prefix: modules/auth
    branch: splits/auth-module
    installed_version: v0.62.0
    installed_at: 2025-10-23
  billing:
    prefix: modules/billing
    branch: splits/billing-module
    installed_version: v0.64.0
    installed_at: 2025-10-25
```

**4. Core Commands (Implemented in v0.61.0)**:

`quickscale embed --module auth` - Embed module via split branch
- **Implementation**: `git subtree add --prefix=modules/auth <remote> splits/auth-module --squash`
- **Technical details**:
  - Check if git repository
  - Verify module exists (check remote branch)
  - Verify no existing `modules/auth/` directory
  - Add subtree from split branch
  - Update `.quickscale/config.yml` with module metadata
  - Show success message with INSTALLED_APPS instructions
- **Example**:
```bash
cd myproject/
quickscale embed --module auth
# Output:
# Embedding auth module from splits/auth-module...
# Module installed to: modules/auth/
#
# Next steps:
# 1. Add to INSTALLED_APPS in settings/base.py:
#    INSTALLED_APPS = [..., "modules.auth"]
# 2. Run migrations: python manage.py migrate
```

`quickscale update` - Update all installed modules
- **Implementation**: Read `.quickscale/config.yml`, run `git subtree pull` for each module
- **Technical details**:
  - Read installed modules from config
  - For each module: `git subtree pull --prefix=modules/{name} <remote> splits/{name}-module --squash`
  - Show diff summary before pulling
  - Handle conflicts per module
  - Update version in config
- **Example**:
```bash
cd myproject/
quickscale update
# Output:
# Found 2 installed modules: auth, billing
#
# Updating auth module...
#   - Fixed email verification bug
#   - Added Google OAuth provider
#
# Updating billing module...
#   - Updated Stripe API to latest version
#
# Continue? (y/N):
```

`quickscale push` - Contribute improvements to specific module
- **Implementation**: `git subtree push --prefix=modules/auth <remote> feature/my-improvement`
- **Technical details**:
  - Detect which module has changes
  - Push to feature branch in main repo (not split branch)
  - Maintainer merges to main, auto-split updates split branch
- **Example**:
```bash
cd myproject/
quickscale push --module auth
# Output:
# Detected changes in modules/auth/
# Branch name [feature/auth-improvements]:
# Pushing to https://github.com/<org>/quickscale.git...
#
# Create PR: https://github.com/<org>/quickscale/pull/new/feature/auth-improvements
```

**5. Implementation Structure (v0.61.0)**:

`quickscale_cli/commands/module_commands.py`:
```python
class ModuleEmbedCommand(Command):
    """Embed module via git subtree from split branch."""

    def execute(self, module_name: str, remote: str = None) -> None:
        # 1. Validate git repository
        # 2. Check module exists on remote
        # 3. Verify no existing modules/{module_name}/
        # 4. Verify working directory clean
        # 5. Execute: git subtree add --prefix=modules/{module_name}
        #             {remote} splits/{module_name}-module --squash
        # 6. Update .quickscale/config.yml
        # 7. Show success message with INSTALLED_APPS instructions
```

`quickscale_cli/utils/git_utils.py`:
```python
def is_git_repo() -> bool:
    """Check if current directory is a git repository."""

def is_working_directory_clean() -> bool:
    """Check if there are uncommitted changes."""

def check_remote_branch_exists(remote: str, branch: str) -> bool:
    """Check if branch exists on remote."""

def run_git_subtree_add(prefix: str, remote: str, branch: str) -> None:
    """Execute git subtree add with error handling."""

def run_git_subtree_pull(prefix: str, remote: str, branch: str) -> None:
    """Execute git subtree pull with error handling."""
```

#### **Implementation Tasks (v0.61.0)**

**Module Management Commands**:
- [ ] Implement `quickscale embed --module <name>` command
- [ ] Implement `quickscale update` command (updates installed modules only)
- [ ] Implement `quickscale push --module <name>` command
- [ ] Create `module_commands.py` with embed/update/push logic
- [ ] Create `git_utils.py` with subtree helpers
- [ ] Add `.quickscale/config.yml` configuration tracking
- [ ] Implement safety checks (clean working directory, module exists, etc.)
- [ ] Add interactive confirmation prompts with diff previews

**GitHub Actions - Split Branch Automation**:
- [ ] Create `.github/workflows/split-modules.yml`
- [ ] Auto-split on version tags (v0.*)
- [ ] Split each module: auth, billing, teams, notifications
- [ ] Push splits to `splits/{module}-module` branches
- [ ] Add workflow tests to verify splits work

**Module Safety Features**:
- [ ] Pre-update diff preview (per module)
- [ ] Verify only `modules/*` affected by updates
- [ ] Conflict detection and handling (per module)
- [ ] Rollback/abort functionality
- [ ] Post-update summary of changes

**Documentation**:
- [ ] Update `user_manual.md` with module embed/update workflow
- [ ] Update `decisions.md` CLI Command Matrix (mark v0.61.0 commands as IN)
- [ ] Document split branch architecture
- [ ] Create "Module Management Guide"
- [ ] Document conflict resolution workflow
- [ ] Add troubleshooting for common git issues

**Testing**:
- [ ] Unit tests for module commands (70% coverage per file)
- [ ] Integration tests with test git repositories and split branches
- [ ] E2E test: embed module → update → verify isolation
- [ ] Test conflict scenarios
- [ ] Test error handling (not a git repo, dirty working directory, module doesn't exist)
- [ ] Automated test: verify user's templates/ and project code never modified by module updates

---

### v0.74.0: Module Workflow Validation & Real-World Testing

**Objective**: Validate that module updates work safely in real client projects and don't affect user's custom code.

**Timeline**: After v0.73.0 (advanced module management)

**Rationale**: Module embed/update commands implemented in v0.62.0. This release validates those commands work safely in production after real usage across multiple client projects.

**Success Criteria**:
- Automated tests verify user's `templates/`, `static/`, and project code never modified by module updates
- Module update workflow documented with real project examples
- Safety features prevent accidental code modification
- Rollback procedure documented and tested
- Case studies from 3+ client projects using modules

**Implementation Tasks**:

**Real-World Validation**:
- [ ] Embed modules in 3+ client projects
- [ ] Test module updates across different project structures
- [ ] Document edge cases and conflicts discovered in production
- [ ] Create migration guides for module version upgrades
- [ ] Validate split branch workflow scales with multiple modules

**Safety Validation**:
- [ ] Automated test: verify user's templates/ never modified by module updates
- [ ] Automated test: verify user's static/ never modified by module updates
- [ ] Automated test: verify user's project code never modified by module updates
- [ ] Test module updates don't break custom user modifications
- [ ] Document safe update workflow with real examples

**Testing**:
- [ ] E2E test: embed multiple modules → update → verify isolation
- [ ] Test conflict scenarios (user modified module code) and resolution
- [ ] Test rollback functionality
- [ ] Test module updates across different Django versions
- [ ] Performance testing: update speed with 5+ modules

**Documentation**:
- [ ] Create "Safe Module Updates" guide with screenshots
- [ ] Document conflict resolution workflows with examples
- [ ] Document rollback procedure
- [ ] Create case studies from client projects
- [ ] Add troubleshooting guide for common module update issues

---

#### Pattern Extraction Workflow

#### **When to Extract a Module**
✅ **Extract when**:
- You've built the same feature 2-3 times across client projects
- The code is stable and battle-tested
- The pattern is genuinely reusable (not client-specific)
- The feature would benefit from centralized updates

❌ **Don't extract when**:
- You've only built it once
- It's highly client-specific
- You're just guessing it might be useful
- The code is still experimental or changing rapidly

#### **Extraction Process**
1. **Identify Reusable Code**: Look for repeated patterns across client projects
2. **Create Module Structure**: `quickscale_modules/<module_name>/` in your monorepo
3. **Extract & Refactor**: Move code, make it generic, add tests
4. **Update Client Projects**: Replace custom code with module via git subtree
5. **Document**: Add module documentation and usage examples

**Git Subtree Commands**: See [decisions.md Git Subtree Workflow](./decisions.md#integration-note-personal-toolkit-git-subtree) for authoritative manual commands.

**Note**: CLI wrapper commands for extraction/sync remain Post-MVP. Evaluate after establishing extraction workflow.

---

#### Module Creation Guide (for v0.5x.0 releases)

**Don't build these upfront. Build them when you actually need them 2-3 times.**

#### **Prioritized Module Development Sequence** (based on competitive analysis):

**Phase 2 Priorities** (see [competitive_analysis.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials)):

1. **🔴 P1: `quickscale_modules.auth`** (First module - core features only)
  - v0.65.0: Core django-allauth integration (email/password auth only)
  - v0.65.0: Custom User model patterns and account management views
  - post-v0.65.0: Production email verification workflows and deliverability
  - **Rationale**: Every SaaS needs auth; Pegasus proves django-allauth is correct choice
  - **Delivery Phasing**: Validate basic auth patterns (v0.65.0) then add email (post-v0.65.0)

2. **🔴 P1: `quickscale_modules.billing`** (v0.64.0)
   - Wraps dj-stripe for Stripe subscriptions
   - Plans, pricing tiers, trials
   - Webhook handling with logging
   - Invoice management
   - **Rationale**: Core SaaS monetization; Stripe-only reduces complexity

3. **🔴 P1: `quickscale_modules.teams`** (v0.69.0)
   - Multi-tenancy patterns (User → Team → Resources)
   - Role-based permissions (Owner, Admin, Member)
   - Invitation system with email tokens
   - Row-level security query filters
   - **Rationale**: Most B2B SaaS requires team functionality

4. **🟡 P2: `quickscale_modules.notifications`** (v0.72.0)
   - Wraps django-anymail for multiple email backends
   - Transactional email templates
   - Async email via Celery
   - Email tracking scaffolding

5. **🟡 P2: `quickscale_modules.api`** (Fifth module, if needed)
   - Wraps Django REST framework
   - Authentication patterns
   - Serializer base classes

**Extraction Rule**: Only build after using 2-3 times in real client projects. Don't build speculatively.

**Competitive Context**: This sequence matches successful competitors' feature prioritization while maintaining QuickScale's reusability advantage. See [competitive_analysis.md Strategic Recommendations](../overview/competitive_analysis.md#strategic-recommendations).

#### **Admin Module Scope**

The admin module scope has been defined in [decisions.md Admin Module Scope Definition](./decisions.md#admin-module-scope-definition).

**Summary**: Enhanced Django admin interface with custom views, system configuration, monitoring dashboards, and audit logging. Distinct from auth module (user authentication/authorization).

#### **Module Creation Checklist**:
- [ ] Used successfully in 2-3 client projects
- [ ] Code is stable and well-tested
- [ ] Genuinely reusable (not client-specific hacks)
- [ ] Documented with examples and integration guide
- [ ] Distributed via git subtree to other projects
- [ ] Consider PEP 420 namespace packages if multiple modules exist

**Module Structure Reference**: See [scaffolding.md §4 (Post-MVP Modules)](./scaffolding.md#post-mvp-structure) for canonical package layout.

---

#### Module Management Enhancements (Post v0.73.0 / Future)

**Note**: Basic module management commands (`quickscale embed --module <name>`, `quickscale update`, `quickscale push`) are implemented in **v0.62.0**. Advanced features planned for **v0.73.0**. This section discusses potential future enhancements beyond v0.73.0.

Based on usage feedback after v0.73.0 implementation, consider these enhancements:

**Future Enhancements** (evaluate after v0.69.0 ships and gets real usage in production):
- [ ] **Module versioning and compatibility**
  - [ ] `quickscale embed --module auth@v0.62.0` - Pin specific module version
  - [ ] Semantic versioning compatibility checks
  - [ ] Automatic migration scripts for breaking changes
- [ ] **Document versioning strategy**
  - [ ] Git tags for stable snapshots (e.g., `core-v0.57.0`)
  - [ ] Semantic versioning for modules
  - [ ] Compatibility tracking between core and modules
- [ ] **Create extraction helper scripts** (optional)

**Success Criteria (example)**: Implement CLI helpers when one or more of the following are true:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation.

(Adjust thresholds based on observed usage and community feedback.)
  - [ ] Script to assist moving code from client project to quickscale_modules/
  - [ ] Validation script to check module structure

**Note**: Only build these if the manual workflow becomes a bottleneck. Don't automate prematurely.

---

#### Configuration System Evaluation (potential v0.6x.0 release)

**After 5+ client projects**, evaluate if YAML config would be useful.

**Questions to answer**:
- Do you find yourself repeating the same Django settings setup?
- Would declarative config speed up project creation?
- Is Django settings inheritance working well enough?
- Would non-developers benefit from YAML-based project config?

**Decision Point**: Add YAML config ONLY if it solves real pain points from MVP usage.

**If pursuing**:
- [ ] Define minimal configuration schema (see [decisions.md illustrative schemas](./decisions.md#architectural-decision-configuration-driven-project-definition))
- [ ] Implement config loader and validator
- [ ] Create CLI commands: `quickscale validate`, `quickscale generate`
- [ ] Update templates to support config-driven generation
- [ ] Document configuration options

---

### v1.0.0+: Community Platform (Optional Evolution)

**🎯 Objective**: IF proven successful personally, evolve into community platform.

**Timeline**: 12-18+ months after MVP (or never, if personal toolkit is enough)

**Version Strategy**: Major version (v1.0.0) for community platform features

**Example Release Sequence**:
- **v1.0.0**: PyPI publishing + package distribution
- **v1.1.0**: Theme package system
- **v1.2.0**: Marketplace basics
- **v1.x.0**: Advanced community features

**Prerequisites Before Starting v1.0.0**:
- ✅ 10+ successful client projects built with QuickScale
- ✅ 5+ proven reusable modules extracted
- ✅ Clear evidence that others want to use your patterns
- ✅ Bandwidth to support community and marketplace

#### v1.0.0: Package Distribution

When you're ready to share with community:

- [ ] **Setup PyPI publishing for modules**
  - [ ] Convert git subtree modules to pip-installable packages
  - [ ] Use PEP 420 implicit namespaces (`quickscale_modules.*`)
  - [ ] Implement semantic versioning and compatibility tracking
  - [ ] Create GitHub Actions for automated publishing
- [ ] **Create private PyPI for commercial modules** (see [commercial.md](../overview/commercial.md))
  - [ ] Set up private package repository
  - [ ] Implement license validation for commercial modules
  - [ ] Create subscription-based access system
- [ ] **Document package creation for community contributors**
  - [ ] Package structure guidelines
  - [ ] Contribution process
  - [ ] Quality standards and testing requirements

---

#### v1.1.0: Theme Package System

If reusable business logic patterns emerge:

- [ ] **Create theme package structure** (`quickscale_themes.*`)
  - [ ] Define theme interface and base classes
  - [ ] Implement theme inheritance system
  - [ ] Create theme packaging guidelines
- [ ] **Create example themes**
  - [ ] `quickscale_themes.starter` - Basic starter theme
  - [ ] `quickscale_themes.todo` - TODO app example
  - [ ] Document theme customization patterns
- [ ] **Document theme creation guide**
  - [ ] Theme architecture overview
  - [ ] Base model and business logic patterns
  - [ ] Frontend integration guidelines

**Theme Structure Reference**: See [scaffolding.md §4 (Post-MVP Themes)](./scaffolding.md#post-mvp-structure).

---

#### v1.2.0: Marketplace & Community

Only if there's real demand:

- [ ] **Build package registry/marketplace**
  - [ ] Package discovery and search
  - [ ] Ratings and reviews system
  - [ ] Module/theme compatibility tracking
- [ ] **Create community contribution guidelines**
  - [ ] Code of conduct
  - [ ] Contribution process and standards
  - [ ] Issue and PR templates
- [ ] **Setup extension approval process**
  - [ ] Quality review checklist
  - [ ] Security audit process
  - [ ] Compatibility verification
- [ ] **Build commercial module subscription system**
  - [ ] License management
  - [ ] Payment integration
  - [ ] Customer access control

See [commercial.md](../overview/commercial.md) for detailed commercial distribution strategies.

---

#### v1.3.0: Advanced Configuration

If YAML config proves useful in Phase 2:

- [ ] **Implement full configuration schema**
  - [ ] Module/theme selection via config
  - [ ] Environment-specific overrides
  - [ ] Customization options
- [ ] **Add module/theme selection via config**
  - [ ] Declarative module dependencies
  - [ ] Theme selection and variants
- [ ] **Create migration tools for config updates**
  - [ ] Schema version migration scripts
  - [ ] Backward compatibility checks
- [ ] **Build configuration validation UI** (optional)
  - [ ] Web-based config editor
  - [ ] Real-time validation
  - [ ] Preview generated project

**IMPORTANT**: v1.0.0+ is OPTIONAL. Many successful solo developers and agencies never need a community platform. Evaluate carefully before investing in marketplace features.

---
