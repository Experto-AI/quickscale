# Release v0.64.0: Starter HTML Theme Showcase Architecture

**Release Date**: October 31, 2025
**Status**: 🔄 READY FOR IMPLEMENTATION
**Objective**: Add module showcase architecture to starter HTML theme - establishes pattern for all future modules

---

## Why v0.64.0 (Showcase as Separate Release)?

**v0.63.0 Status**: Production-ready authentication module with 89% test coverage and complete auth flows. Released October 29, 2025.

**v0.64.0 Focus**: The starter HTML theme currently shows a basic "Next Steps" page. This release transforms it into a **module showcase architecture** that demonstrates QuickScale's composability.

**Strategic Importance**: The showcase architecture is critical for:
1. **Marketing**: Users immediately see what QuickScale offers
2. **Discovery**: Users understand what modules to install next
3. **Education**: Clear demonstrations of each module's capabilities
4. **Proof of concept**: Visual validation of QuickScale's modular architecture

**Decision**: Keep v0.63.0 as-is (auth module complete), add showcase in v0.64.0 as a clean upgrade path. This allows:
- ✅ Review v0.63.0 independently (auth module quality validation)
- ✅ Test showcase separately without risk to auth module
- ✅ Users on v0.63.0 can upgrade incrementally (optional, not required)
- ✅ Establishes showcase pattern before v0.65.0 (email verification)

---

## What v0.64.0 Adds (No Auth Module Changes)

### ✅ Keeping (No Changes - v0.63.0 Complete)
- Auth module code in `quickscale_modules/auth/` (89% test coverage, already validated)
- django-allauth integration with custom User model (production-ready)
- All authentication flows (login, logout, signup, password reset, profile)
- Interactive embed configuration
- Module templates and static files
- Test suite (13 passing tests)
- Module README and documentation

**Key Point**: v0.64.0 does NOT touch auth module code at all. That remains stable from v0.63.0.

### 🆕 Adding (New in v0.64.0 - Theme Layer Only)
- **Starter HTML Theme Showcase Landing Page** (`themes/starter_html/templates/index.html.j2`)
  - Module showcase grid layout
  - Auth module card (🔐 Authentication)
  - Placeholder cards for billing, teams, notifications (marked "Available")
  - Status indicators (Installed vs Available)
- **Auth Preview Page** (`themes/starter_html/templates/auth_preview.html.j2`)
  - Detailed auth features showcase
  - Works WITHOUT auth module installed
  - Shows installation instructions
  - Links to functional pages when installed
- **Module Detection Context Processor** (`quickscale_core/context_processors.py`)
  - Provides `modules` dict to all templates
  - Enables dynamic showcase behavior
- **Showcase CSS Styles** (`themes/starter_html/static/css/style.css.j2`)
  - Module card styles with hover effects
  - Responsive grid layout
  - Status badges (installed/available)
  - Preview page styles
- **Updated Base Template** (`themes/starter_html/templates/base.html.j2`)
  - Navigation with "Modules" section
  - Dynamic links based on installation status

---

## Implementation Tasks (v0.64.0 - Theme Layer Only)

**IMPORTANT**: All existing auth module code remains unchanged. v0.64.0 tasks focus ONLY on the starter HTML theme showcase layer.

### Task Group 1: Showcase Landing Page (index.html.j2)

**File**: `quickscale_core/src/quickscale_core/generator/templates/themes/starter_html/templates/index.html.j2`

**Current State**: Basic "Next Steps" list with Django documentation links

**Target State**: Module showcase with cards for all available modules

**Tasks**:
- [ ] Replace welcome content with hero section:
  - [ ] H1: "Welcome to {{ project_name }}"
  - [ ] Tagline: "Built with QuickScale - Compose your Django SaaS"
- [ ] Add modules showcase section:
  - [ ] Section header: "Available Modules"
  - [ ] Grid layout for module cards (CSS Grid, responsive)
- [ ] Create auth module card:
  - [ ] Icon: 🔐
  - [ ] Title: "Authentication"
  - [ ] Description: "User authentication with django-allauth"
  - [ ] Features list: Email/password login, Password reset flows, Profile management
  - [ ] Demo button: "View Features" (links to /auth/preview/)
  - [ ] Status badge: Shows "✓ Installed" if auth module embedded, else "Install with: quickscale embed --module auth"
  - [ ] Conditional CSS classes: `.installed` or `.available`
- [ ] Create placeholder cards for future modules:
  - [ ] **Billing** (💳): Stripe integration, subscriptions, invoices
  - [ ] **Teams** (👥): Multi-tenancy, permissions, invitations
  - [ ] **Notifications** (🔔): Email infrastructure, in-app notifications
  - [ ] All marked as `.available` with installation commands
- [ ] Add template logic for module detection:
  - [ ] Use `{% if modules.auth %}` from context processor
  - [ ] Dynamically set CSS classes and status text
  - [ ] Show appropriate button text and links

**Example Structure**:
```html
{%raw%}{% extends "base.html" %}
{% load static %}

{% block title %}Welcome to {% endraw %}{{ project_name }}{%raw%}{% endblock %}

{% block content %}
<!-- Hero Section -->
<div class="hero">
  <h1>Welcome to {% endraw %}{{ project_name }}{%raw%}</h1>
  <p class="tagline">Built with QuickScale - Compose your Django SaaS</p>
</div>

<!-- Modules Showcase -->
<section class="modules-showcase">
  <h2>Available Modules</h2>
  <div class="module-grid">

    <!-- Auth Module Card -->
    <div class="module-card {% if modules.auth %}installed{% else %}available{% endif %}">
      <h3>🔐 Authentication</h3>
      <p class="module-description">User authentication with django-allauth</p>
      <ul class="features">
        <li>Email/password login</li>
        <li>Password reset flows</li>
        <li>Profile management</li>
      </ul>
      {% if modules.auth %}
        <a href="/accounts/login/" class="btn-demo">View Features</a>
        <span class="status installed">✓ Installed</span>
      {% else %}
        <a href="{% url 'auth_preview' %}" class="btn-demo">Preview Demo</a>
        <span class="status available">Install with: <code>quickscale embed --module auth</code></span>
      {% endif %}
    </div>

    <!-- Billing Module Card (placeholder) -->
    <div class="module-card available">
      <h3>💳 Billing & Subscriptions</h3>
      <p class="module-description">Stripe integration with subscription management</p>
      <ul class="features">
        <li>Multiple pricing tiers</li>
        <li>Usage tracking</li>
        <li>Invoice management</li>
      </ul>
      <a href="{% url 'billing_preview' %}" class="btn-demo">Preview Demo</a>
      <span class="status available">Coming in v0.65.0 - <code>quickscale embed --module billing</code></span>
    </div>

    <!-- Teams Module Card (placeholder) -->
    <div class="module-card available">
      <h3>👥 Teams & Multi-tenancy</h3>
      <p class="module-description">Collaborative workspaces with role-based permissions</p>
      <ul class="features">
        <li>Team creation & management</li>
        <li>Member invitations</li>
        <li>Role-based permissions</li>
      </ul>
      <a href="{% url 'teams_preview' %}" class="btn-demo">Preview Demo</a>
      <span class="status available">Coming in v0.66.0 - <code>quickscale embed --module teams</code></span>
    </div>

    <!-- Notifications Module Card (placeholder) -->
    <div class="module-card available">
      <h3>🔔 Notifications</h3>
      <p class="module-description">Email infrastructure and in-app notifications</p>
      <ul class="features">
        <li>Transactional emails</li>
        <li>In-app notifications</li>
        <li>Notification preferences</li>
      </ul>
      <a href="{% url 'notifications_preview' %}" class="btn-demo">Preview Demo</a>
      <span class="status available">Coming in v0.69.0 - <code>quickscale embed --module notifications</code></span>
    </div>

  </div>
</section>

<!-- Resources Section (keep existing) -->
<section class="resources">
  <h2>Resources</h2>
  <ul>
    <li><a href="https://docs.djangoproject.com/" target="_blank">Django Documentation</a></li>
    <li><a href="https://github.com/Experto-AI/quickscale" target="_blank">QuickScale Documentation</a></li>
  </ul>
</section>
{% endblock %}{%endraw%}
```

---

### Task Group 2: Auth Preview Page Template

**File**: `quickscale_core/src/quickscale_core/generator/templates/themes/starter_html/templates/auth_preview.html.j2`

**Purpose**: Show auth module features WITHOUT requiring the module to be installed. Works as marketing/demo page.

**Tasks**:
- [ ] Create new template file
- [ ] Extend base.html
- [ ] Add preview header:
  - [ ] Title: "🔐 Authentication Module"
  - [ ] Tagline: "Complete user authentication flows with django-allauth"
- [ ] Add installation status check:
  - [ ] If installed: Success alert with link to /accounts/login/
  - [ ] If not installed: Info alert with installation command
- [ ] Create feature showcases (4 sections):
  - [ ] **Section 1: Login & Signup**
    - [ ] Description of email/password authentication
    - [ ] Mockup or description of login/signup forms
  - [ ] **Section 2: Password Management**
    - [ ] Description of password reset flows
    - [ ] Email-based password recovery
  - [ ] **Section 3: Profile Management**
    - [ ] User profile viewing and editing
    - [ ] Account settings
  - [ ] **Section 4: Account Security**
    - [ ] Account deletion
    - [ ] Session management
- [ ] Add installation instructions section:
  - [ ] Step 1: Run `quickscale embed --module auth`
  - [ ] Step 2: Answer configuration prompts
  - [ ] Step 3: Restart development server
  - [ ] Step 4: Visit /accounts/login/
- [ ] Add footer with documentation link

**Example Structure**:
```html
{%raw%}{% extends "base.html" %}
{% load static %}

{% block title %}Authentication Module - Preview{% endblock %}

{% block content %}
<div class="preview-container">
  <header class="preview-header">
    <h1>🔐 Authentication Module</h1>
    <p class="tagline">Complete user authentication flows with django-allauth</p>
  </header>

  {% if modules.auth %}
    <div class="alert success">
      ✓ Authentication module is installed. <a href="/accounts/login/">Go to Login</a>
    </div>
  {% else %}
    <div class="alert info">
      This is a preview. Install with: <code>quickscale embed --module auth</code>
    </div>
  {% endif %}

  <section class="feature-showcase">
    <h2>Login & Signup Flows</h2>
    <div class="feature-demo">
      <p>Secure email/password authentication powered by django-allauth:</p>
      <ul>
        <li>Email-based login (or username, configurable)</li>
        <li>Registration with validation</li>
        <li>Automatic session management</li>
        <li>Remember me functionality</li>
      </ul>
    </div>
  </section>

  <section class="feature-showcase">
    <h2>Password Management</h2>
    <div class="feature-demo">
      <p>Complete password recovery and security features:</p>
      <ul>
        <li>Email-based password reset</li>
        <li>Secure token generation</li>
        <li>Password change for logged-in users</li>
        <li>Password strength validation</li>
      </ul>
    </div>
  </section>

  <section class="feature-showcase">
    <h2>Profile Management</h2>
    <div class="feature-demo">
      <p>User profile viewing and editing:</p>
      <ul>
        <li>View user profile</li>
        <li>Edit profile information</li>
        <li>Custom User model (extends AbstractUser)</li>
        <li>Easy to extend with additional fields</li>
      </ul>
    </div>
  </section>

  <section class="feature-showcase">
    <h2>Account Security</h2>
    <div class="feature-demo">
      <p>Account management and security features:</p>
      <ul>
        <li>Account deletion with confirmation</li>
        <li>Session management</li>
        <li>Logout functionality</li>
        <li>Account inactive handling</li>
      </ul>
    </div>
  </section>

  <section class="installation">
    <h2>Installation</h2>
    <ol>
      <li>Run: <code>quickscale embed --module auth</code></li>
      <li>Answer configuration prompts:
        <ul>
          <li>Enable user registration? [Y/n]</li>
          <li>Email verification [none/optional/mandatory]</li>
          <li>Authentication method [email/username/both]</li>
        </ul>
      </li>
      <li>Restart your development server</li>
      <li>Visit <code>/accounts/login/</code> to start using authentication</li>
    </ol>
  </section>

  <footer class="preview-footer">
    <a href="/modules/auth/README.md" class="btn">View Full Documentation</a>
  </footer>
</div>
{% endblock %}{%endraw%}
```

---

### Task Group 3: Context Processor for Module Detection

**File**: `quickscale_core/src/quickscale_core/context_processors.py` (NEW FILE)

**Purpose**: Provide module installation status to all templates for dynamic showcase behavior.

**Tasks**:
- [ ] Create new file in `quickscale_core/src/quickscale_core/`
- [ ] Implement `installed_modules()` function
- [ ] Check `settings.INSTALLED_APPS` for module presence
- [ ] Return dict with boolean flags for each module
- [ ] Add QuickScale version info
- [ ] Add docstrings following Google style
- [ ] Add type hints

**Implementation**:
```python
"""Context processors for QuickScale themes."""

from django.conf import settings
from django.http import HttpRequest
from typing import Dict, Any


def installed_modules(request: HttpRequest) -> Dict[str, Any]:
    """Provide module installation status to all templates

    This context processor checks which QuickScale modules are installed
    and makes that information available to all templates for dynamic
    showcase behavior and navigation.
    """
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

**Integration Task**:
- [ ] Update generated project settings template to include context processor:
  - [ ] File: `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2`
  - [ ] Add to `TEMPLATES[0]['OPTIONS']['context_processors']`:
    ```python
    'quickscale_core.context_processors.installed_modules',
    ```

---

### Task Group 4: Showcase CSS Styles

**File**: `quickscale_core/src/quickscale_core/generator/templates/themes/starter_html/static/css/style.css.j2`

**Current State**: Basic styles for header, main, footer

**Tasks**:
- [ ] Add hero section styles
- [ ] Add modules showcase grid styles (CSS Grid, responsive)
- [ ] Add module card styles:
  - [ ] Base card: border, padding, border-radius
  - [ ] Hover effects: shadow, transform, border color change
  - [ ] Installed state: green border, light green background
  - [ ] Available state: blue border, light blue background
- [ ] Add module card content styles:
  - [ ] Title (h3) with icon
  - [ ] Description paragraph
  - [ ] Features list with checkmarks
  - [ ] Demo button (primary blue)
  - [ ] Status badge (installed green / available blue)
- [ ] Add preview page styles:
  - [ ] Preview container: max-width, padding
  - [ ] Preview header: centered, large title
  - [ ] Alert boxes: success (green), info (blue)
  - [ ] Feature showcase sections
  - [ ] Installation instructions section
  - [ ] Footer with CTA button
- [ ] Add responsive breakpoints:
  - [ ] Mobile: 1 column
  - [ ] Tablet: 2 columns
  - [ ] Desktop: 3-4 columns

**Full CSS** (see roadmap.md "Module Showcase Implementation Guide §4" for complete styles)

---

### Task Group 5: Preview Page URL Configuration

**Files**:
- `quickscale_core/src/quickscale_core/generator/templates/project_name/views.py.j2` (NEW FILE)
- `quickscale_core/src/quickscale_core/generator/templates/project_name/urls.py.j2` (UPDATE)

**Tasks**:
- [ ] Create `views.py.j2` template with preview views:
  ```python
  from django.shortcuts import render
  from django.http import HttpRequest, HttpResponse

  def auth_preview(request: HttpRequest) -> HttpResponse:
      """Show authentication module preview page"""
      return render(request, 'auth_preview.html')

  def billing_preview(request: HttpRequest) -> HttpResponse:
      """Show billing module preview page"""
      return render(request, 'billing_preview.html')

  def teams_preview(request: HttpRequest) -> HttpResponse:
      """Show teams module preview page"""
      return render(request, 'teams_preview.html')

  def notifications_preview(request: HttpRequest) -> HttpResponse:
      """Show notifications module preview page"""
      return render(request, 'notifications_preview.html')
  ```

- [ ] Update `urls.py.j2` to include preview routes:
  ```python
  from {{ project_name }} import views

  urlpatterns = [
      # ... existing patterns

      # Module preview pages
      path('auth/preview/', views.auth_preview, name='auth_preview'),
      path('billing/preview/', views.billing_preview, name='billing_preview'),
      path('teams/preview/', views.teams_preview, name='teams_preview'),
      path('notifications/preview/', views.notifications_preview, name='notifications_preview'),
  ]
  ```

---

### Task Group 6: Base Template Updates (Optional)

**File**: `quickscale_core/src/quickscale_core/generator/templates/themes/starter_html/templates/base.html.j2`

**Current State**: Basic header with project name, no navigation

**Optional Enhancement** (Can defer to v0.64.0):
- [ ] Add navigation menu with "Modules" dropdown
- [ ] Show installed modules with links to functional pages
- [ ] Show available modules with links to preview pages
- [ ] Add visual indicators (✓ for installed, ⚠ for available)

**Decision**: Defer to keep scope focused. Landing page showcase is sufficient for v0.63.0 re-implementation.

---

## Testing & Validation

### Manual Testing Checklist

**Scenario 1: Fresh project without modules**
- [ ] Run `quickscale init testproject`
- [ ] Start development server
- [ ] Visit http://localhost:8000/
- [ ] Verify showcase landing page renders correctly
- [ ] Verify all 4 module cards show "Available" status
- [ ] Click "Preview Demo" on auth card
- [ ] Verify auth preview page loads
- [ ] Verify installation instructions are shown

**Scenario 2: Project with auth module embedded**
- [ ] Run `quickscale embed --module auth`
- [ ] Answer configuration prompts
- [ ] Restart development server
- [ ] Visit http://localhost:8000/
- [ ] Verify auth module card shows "Installed" status (✓ Installed)
- [ ] Verify auth card button says "View Features" (not "Preview Demo")
- [ ] Click "View Features" button
- [ ] Verify it links to /accounts/login/ (functional page)
- [ ] Visit http://localhost:8000/auth/preview/
- [ ] Verify preview page shows success alert: "Authentication module is installed"

**Scenario 3: Preview pages for unimplemented modules**
- [ ] Visit http://localhost:8000/billing/preview/
- [ ] Verify placeholder preview page renders (even though billing module doesn't exist yet)
- [ ] Same for teams and notifications preview pages

**Scenario 4: Responsive design**
- [ ] Test on mobile viewport (320px-480px)
- [ ] Verify module cards stack in 1 column
- [ ] Test on tablet viewport (768px-1024px)
- [ ] Verify module cards display in 2 columns
- [ ] Test on desktop viewport (1280px+)
- [ ] Verify module cards display in 3-4 columns

### Automated Testing

**Test Coverage Requirements**:
- Context processor: Test `installed_modules()` returns correct dict
- Preview views: Test each preview view returns 200 status
- Template rendering: Test showcase renders without errors
- Module detection: Test template logic for installed/available states

**Test Files**:
- [ ] `quickscale_core/tests/test_context_processors.py` (NEW)
- [ ] `quickscale_core/tests/test_showcase_views.py` (NEW)
- [ ] `quickscale_core/tests/test_showcase_templates.py` (NEW)

---

## Success Criteria (v0.64.0)

### Functional Requirements
- ✅ Fresh project shows showcase landing page with 4 module cards
- ✅ Module cards display correct status (installed vs available)
- ✅ Preview pages work for all modules (auth, billing, teams, notifications)
- ✅ Auth preview page shows installation instructions when not installed
- ✅ Auth preview page shows success message when installed
- ✅ Module cards link to preview pages when not installed
- ✅ Module cards link to functional pages when installed

### Quality Requirements
- ✅ All existing auth module tests still pass (13 tests, 89% coverage)
- ✅ New context processor has 100% test coverage
- ✅ Preview views have 100% test coverage
- ✅ CSS passes validation (no errors)
- ✅ HTML templates pass validation
- ✅ Responsive design works on mobile, tablet, desktop
- ✅ Code quality passes: Ruff format/check

### Documentation Requirements
- ✅ Roadmap updated with Module Showcase Implementation Guide
- ✅ All future module releases reference showcase requirements
- ✅ This re-implementation plan documents the changes
- ✅ Updated release-v0.63.0-implementation.md reflects showcase additions

---

## Deliverables (v0.64.0)

### Code Changes
1. ✅ Updated `index.html.j2` with showcase landing page
2. ✅ New `auth_preview.html.j2` template
3. ✅ New `context_processors.py` for module detection
4. ✅ Updated `style.css.j2` with showcase styles
5. ✅ New `views.py.j2` with preview views
6. ✅ Updated `urls.py.j2` with preview routes
7. ✅ Updated settings template to register context processor

### Testing
1. ✅ New context processor tests
2. ✅ New preview view tests
3. ✅ Manual QA checklist completed
4. ✅ All existing tests still pass

---

## Timeline Estimate

**Total Effort**: 6-8 hours

**Breakdown**:
- Task Group 1 (Landing Page): 2 hours
- Task Group 2 (Preview Page): 1.5 hours
- Task Group 3 (Context Processor): 1 hour
- Task Group 4 (CSS Styles): 1.5 hours
- Task Group 5 (URL Configuration): 0.5 hours
- Testing & Validation: 1.5 hours
- Documentation: 1 hour

**Target Completion**: Same day (October 31, 2025)

---

## Next Steps

1. ✅ Review this v0.64.0 implementation plan
2. ⏳ Implement Task Groups 1-6 (showcase architecture)
3. ⏳ Run manual testing checklist
4. ⏳ Write automated tests for new components
5. ⏳ Create release-v0.64.0-implementation.md documenting completion
6. ⏳ Commit with message: "Release v0.64.0: Add module showcase architecture to starter HTML theme"
7. ⏳ Proceed to v0.65.0 planning (auth email verification)

---

## Migration Path from v0.63.0

**For existing v0.63.0 projects**:
- ✅ Continue working unchanged - showcase is optional
- ✅ Auth module remains fully functional
- ✅ No breaking changes
- 🔧 To upgrade: Copy new theme templates manually (optional)

**For new projects**:
- ✅ Generate with v0.64.0+ to get showcase automatically
- ✅ Showcase works whether modules installed or not

---

## References

- **v0.63.0 Implementation**: `docs/releases/release-v0.63.0-implementation.md` (auth module complete)
- **Roadmap**: `docs/technical/roadmap.md` (Module Showcase Implementation Guide, v0.64.0 section)
- **Architecture**: `docs/technical/decisions.md` (Module & Theme Architecture)
- **Scaffolding**: `docs/technical/scaffolding.md` (Theme Structure)
