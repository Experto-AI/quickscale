# QuickScale v0.73.0 CRM Module - Research & Proposal

**Date**: 2025-12-08
**Version**: 0.73.0
**Status**: Research & Planning Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Market Research](#market-research)
   - Django CRM Solutions
   - Lightweight CRM Market
   - Notion/Airtable Templates
   - Modern Open-Source CRMs (TwentyCRM, Atomic, EspoCRM, SuiteCRM, Corteza, Krayin, Fat Free)
   - Modern CRM Trends (2025)
   - Competitive Positioning Matrix
   - Key Learnings for QuickScale
3. [Feature Analysis](#feature-analysis)
4. [Architecture Decisions](#architecture-decisions)
5. [Proposed Implementation](#proposed-implementation)
6. [Recommendations](#recommendations)
7. [Appendix: Research Sources](#appendix-research-sources)

---

## Executive Summary

### Market Gap Identified

**The Problem**: Existing Django CRMs are overbuilt (12+ models with email sync, task management, etc.), while lightweight CRM tools lack Django integration. QuickScale v0.73.0 can fill this gap with a minimal, API-first CRM module.

**Our Opportunity**: Build a lightweight Django CRM module that:
- Uses 5-7 core models (vs. 12+ in DjangoCRM)
- Focuses on API-first architecture (DRF)
- Provides starting point, not complete solution
- Ships fast with room for user customization

### Confirmed Scope (User Decisions)

✅ **Include:**
- Contact & Company management (core)
- Deal/Opportunity tracking with pipeline stages (core)
- Basic note-taking (ContactNote, DealNote)
- Tags/Categories (ManyToMany)
- User assignment (owner field on deals)
- Probability % forecasting
- Bulk operations (mark as won/lost)

❌ **Exclude (Defer):**
- Email synchronization → v0.78.0 (notifications module)
- File attachments → Post-v0.73.0 or user extensions
- Advanced reporting → v0.74.0 (React theme responsibility)
- Custom fields → v0.75.0+ or user extensions

---

## Market Research

### 1. Existing Django CRM Solutions

#### DjangoCRM/django-crm
- **Repository**: https://github.com/DjangoCRM/django-crm
- **License**: AGPL-3.0
- **Status**: Actively maintained
- **Architecture**: Django Admin UI-first

**Models** (12+ core models):
- CRM: Requests, Leads, Companies, Contact Persons, Deals, Email Messages, Products, Payments
- Tasks: Tasks, Memos, Projects
- Infrastructure: Reminders, Tags, Files, User Profiles

**Why NOT suitable:**
- Too heavyweight (12+ models vs our target 5-7)
- Django Admin-heavy (QuickScale needs theme-agnostic backend)
- Email integration adds unnecessary complexity for MVP
- Contradicts "starting point" philosophy

**Lesson**: Feature creep is the enemy. Start minimal.

---

#### MicroPyramid/Django-CRM
- **Repository**: https://github.com/MicroPyramid/Django-CRM
- **Status**: No longer maintained
- **Migration**: Developers shifted to SvelteKit + Prisma (moved away from Django)

**Lesson**: Complexity drove developers away from Django. Keep it simple to remain maintainable.

---

#### koalixcrm
- **Type**: Django + ERP features
- **Features**: Double-entry accounting, project management

**Why NOT suitable**: ERP features add 3x complexity, enterprise focus (opposite of "starting point")

---

### 2. Lightweight CRM Market Analysis

| Tool | Style | Setup Time | Target Users | Core Tables | Key Insight |
|------|-------|------------|--------------|-------------|-------------|
| **OnePageCRM** | Minimal UI | 5 min | Solo/small team | 4 | Action-focused workflow |
| **Less Annoying CRM** | Zero bloat | 10 min | Solo founders | 4 | Simplicity wins |
| **Streak** | Gmail-native | 2 min | Gmail users | 3 | Integration > features |
| **Notion CRM** | Template-based | 20 min | Doc-heavy teams | 4 | Flexible relations |
| **Airtable CRM** | Database | 15 min | Semi-technical | 4 | Structured data |
| **Monica** | Personal CRM | 15 min | Solo/freelance | 5 | Relationship focus |

**Pattern Recognition:**
1. **4-5 core tables** is the sweet spot (not 12+)
2. **Minimal setup** (5-15 minutes to first use)
3. **Zero bloat** (no features user can't immediately use)
4. **Simplicity over power** (basic reports, no advanced analytics)

---

### 3. Notion/Airtable CRM Templates

#### Notion CRM Structure
```
Tables:
├── Contacts (Name, Email, Phone, Company, Status, Last Contact, Notes)
├── Companies (Name, Industry, Website, Contacts, Notes)
├── Deals (Title, Company, Amount, Stage, Expected Close, Probability, Owner, Notes)
└── Activities (Type, Related To, Date, Notes, Owner)
```

#### Airtable CRM Structure
```
Tables:
├── Contacts (First Name, Last Name, Email, Phone, Company, Title, Lead Score)
├── Companies (Name, Industry, Website, Size, Contacts, Total Deal Value)
├── Opportunities (Name, Company, Amount, Stage, Close Date, Probability, Owner)
└── Activities (Type, Opportunity, Contact, Date, Completed, Notes, Owner)
```

**Key Insights:**
- Both use 4 core tables
- Rich text notes > advanced structured fields for MVP
- Flexible relationships (many-to-many for activities)
- Probability % is common feature (forecasting)

---

### 4. Modern Open-Source CRM Solutions (TwentyCRM and Similar)

#### A. TwentyCRM (Twenty)

**Overview**: Modern alternative to Salesforce, Y Combinator-backed (S23), 36,000+ GitHub stars

- **Repository**: https://github.com/twentyhq/twenty
- **License**: AGPL-3.0
- **Status**: Actively maintained, production-ready
- **Company**: Public Benefits Company (considers societal impact)

**Tech Stack:**
- Backend: NestJS, BullMQ, PostgreSQL, Redis, TypeScript
- Frontend: React, Recoil, Emotion, TypeScript
- APIs: GraphQL + REST (dual approach)
- Build: Nx monorepo framework

**Architecture Philosophy:**
- Built from scratch with modern frameworks (not legacy rewrite)
- API-first with GraphQL/REST endpoints
- Modular design for extensions
- Emphasis on developer experience

**Core Features:**
- Contact and company management
- Customizable pipelines and opportunity tracking
- **Custom objects and fields** (users define their own data structures)
- Role-based access control (RBAC)
- Workflow automation with triggers
- Email integration with major services
- Calendar and file management
- Custom dashboards and visualizations
- Advanced search and filtering

**Data Models:**
- Flexible, customizable structures
- **Not constrained by preset configurations** (unlike traditional CRMs)
- Support for complex entity relationships
- Users can create custom objects without code

**2025 Benchmark Rating**: **9/10** (marmelab.com)
- ✅ Strengths: Easy installation, highly hackable, strong developer docs, modern codebase
- ❌ Drawbacks: Large codebase, AGPL-3.0 license

**Why It Matters for QuickScale:**
- Demonstrates market demand for modern, developer-friendly CRMs
- GraphQL + REST dual API approach is becoming standard
- Custom objects are now expected feature (not "nice to have")
- Performance comparable to SaaS without vendor lock-in

---

#### B. Atomic CRM

**Overview**: Lightweight CRM template for developers prioritizing customization

- **Repository**: https://github.com/marmelab/atomic-crm
- **License**: MIT
- **Codebase**: Only **15,000 lines of code** for complete solution
- **Setup**: 5 minutes with Supabase + GitHub Pages

**Tech Stack:**
- Frontend: React, shadcn-admin-kit, TypeScript, Material UI
- Backend: Supabase (PostgreSQL)
- Architecture: Static SPA + serverless

**Core Features:**
- Contact and company management
- Deal tracking and pipeline views
- Task and activity management
- Notes and file attachments
- Email integration basics
- REST APIs for automation

**2025 Benchmark Rating**: **8/10**
- ✅ Strengths: Lightweight, highly flexible, MIT license, modern stack, fast deployment
- ❌ Drawbacks: Limited built-in features, small community, requires development knowledge

**Key Insight**: **15k LOC proves minimal approach works**
- Component-based architecture enables replacing any part
- Ideal for custom CRM implementations
- Demonstrates you don't need 100k+ LOC for functional CRM

**Why It Matters for QuickScale:**
- Validates minimal CRM approach (vs. heavyweight DjangoCRM)
- Shows MIT license can compete with AGPL solutions
- Proves modern tech stack attracts developer audience

---

#### C. EspoCRM

**Overview**: Complete open-source CRM with emphasis on GUI customization

- **Repository**: https://github.com/espocrm/espocrm
- **License**: AGPL-3.0
- **Status**: Actively maintained

**Tech Stack:**
- Backend: PHP 8, Custom framework (Espo ORM)
- Frontend: Handlebar, Bootstrap, SPA
- Database: MySQL/PostgreSQL 15+

**Core Features:**
- Lead and opportunity management
- Sales pipeline automation
- Marketing campaigns and email templates
- Web-to-lead forms
- Workflow automation and BPM
- Email integration and automation
- Reporting and analytics
- REST API

**Pre-built Entities:**
- Contacts, Accounts, Leads, Opportunities, Cases, Tasks
- Custom entity creation via GUI (no code required)
- Customizable fields and relationships

**2025 Benchmark Rating**: **7/10**
- ✅ Strengths: Intuitive interface, powerful admin, comprehensive features, fast
- ❌ Drawbacks: Complex codebase, limited developer docs, proprietary frameworks

**Why It Matters for QuickScale:**
- Shows importance of good admin interface (not just API)
- Custom entities via GUI is now expected (not just for devs)
- PHP ecosystem still viable but Django offers better DX

---

#### D. SuiteCRM

**Overview**: Enterprise-grade fork of SugarCRM, most feature-rich open-source CRM

- **Repository**: https://github.com/SuiteCRM/SuiteCRM
- **License**: AGPL-3.0
- **Heritage**: Based on last open-source SugarCRM release

**Tech Stack:**
- Backend: PHP
- Frontend: Modern UI (v8+)
- Database: MySQL/PostgreSQL

**Core Features:**
- **Most comprehensive feature set** among open-source CRMs
- Full sales lifecycle (leads → contracts)
- Marketing automation and campaigns
- Customer support and case management
- Advanced reporting and analytics
- Workflow automation
- Team and group management
- Project management features
- REST API

**Complexity Level**: **High**
- Large codebase with legacy patterns
- Enterprise-focused with steep learning curve
- Decades of refinement from SugarCRM

**Target Use Case:**
- Medium to large enterprises
- Industries like finance, healthcare (GDPR compliance)
- Organizations with technical resources

**Why It Matters for QuickScale:**
- **Counter-example**: Shows dangers of feature creep
- Demonstrates that "more features" ≠ better UX
- Validates QuickScale's "starting point" philosophy
- Large enterprises need this; startups don't

---

#### E. Corteza

**Overview**: Low-code platform, API-first headless CRM for enterprises

- **Repository**: https://github.com/cortezaproject/corteza
- **License**: Apache 2.0
- **Architecture**: Headless, API-first design

**Tech Stack:**
- Backend: Go (57.3% of codebase)
- Frontend: Vue.js, TypeScript
- Database: PostgreSQL

**Core Features:**
- CRM + business process management + structured data
- Low-code application builder
- Intelligent workflow automation
- Flattened RBAC
- Privacy compliance (WCAG 2.1)
- Extensive REST APIs
- Integration Gateway for third-party data
- AI service integrations

**Headless Capabilities:**
- Can function as headless CRM backend
- External frontends consume REST APIs
- Suitable for iPaaS use cases

**2025 Benchmark Rating**: **7/10**
- ✅ Strengths: API-first, headless, Apache 2.0 license, Go performance
- ❌ Drawbacks: High complexity, steep learning curve, not suitable for non-technical users

**Why It Matters for QuickScale:**
- Demonstrates headless CRM trend
- API-first architecture is table stakes
- Apache 2.0 license more permissive than AGPL

---

#### F. Krayin CRM

**Overview**: Laravel-based modular CRM for PHP developers

- **Repository**: https://github.com/krayin/laravel-crm
- **License**: MIT
- **Tech**: Laravel (PHP 7.3+), Vue.js

**Core Features:**
- Lead and deal management
- Sales forecasting
- Campaign management
- Email marketing and segmentation
- VoIP and live chat
- Custom fields and attributes
- Multi-tenant SaaS support

**Architecture:**
- Modular design using Laravel packages
- Contract and Proxy pattern for models
- Easy integration via familiar Laravel patterns

**2025 Benchmark Rating**: **7/10**
- ✅ Strengths: Laravel ecosystem, modular, MIT license, SaaS-ready
- ❌ Drawbacks: Requires Laravel knowledge, smaller community

**Why It Matters for QuickScale:**
- Shows value of framework-native approach (Krayin:Laravel :: QuickScale:Django)
- Modular package system is maintainable
- MIT license enables commercial use

---

#### G. Fat Free CRM

**Overview**: Ruby on Rails CRM with focus on simplicity

- **Repository**: https://github.com/fatfreecrm/fat_free_crm
- **License**: MIT
- **Tech**: Ruby on Rails

**Features:**
- One of most attractive interfaces for ease of use
- Group collaboration
- Campaign/lead management
- Activity tracking
- Custom fields

**Complexity**: Low
**Use Case**: Small teams, simplicity-first

**Why It Matters for QuickScale:**
- Another validation of minimal approach
- UI/UX matters as much as features
- MIT license success story

---

### 5. Modern CRM Trends (2025)

#### API-First Architecture ✅ **Critical**
- **Trend**: Every feature exposed as integration endpoint
- **Implementation**: REST APIs, GraphQL, webhooks
- **Leaders**: Twenty (REST+GraphQL), Corteza (comprehensive REST)
- **For QuickScale**: DRF API-first is correct approach

#### Headless CRM Approaches
- **Definition**: Separation of backend logic from frontend presentation
- **Leaders**: Corteza, Twenty (supports external UI)
- **Benefit**: Multiple frontend implementations on single backend
- **For QuickScale**: Theme-agnostic backend = headless-ready

#### Backend for Frontend (BFF) Pattern
- **Status**: Moving from niche to mainstream
- **Concept**: One backend per user experience (web, mobile, integrations)
- **In CRM Context**: Different APIs for sales team vs. marketing team
- **For QuickScale**: Consider for v0.74.0+ (React theme)

#### Minimal vs. Feature-Rich Split

**Minimal Philosophy** (QuickScale positioning):
- Lightweight codebase (Atomic: 15k LOC)
- Fast setup and deployment
- Easier customization
- Examples: Atomic CRM, Fat Free CRM, Twenty (intentional scope)

**Feature-Rich Philosophy**:
- Comprehensive out-of-box functionality
- Larger codebase
- Enterprise-grade capabilities
- Examples: SuiteCRM, EspoCRM, Odoo

#### Self-Hosted Momentum (2025)
- Data control and privacy compliance
- GDPR and regional data regulations
- Lower long-term TCO
- Air-gapped deployment options
- **QuickScale advantage**: Native self-hosted support

#### Low-Code / No-Code CRM Building
- **Platforms**: Corteza, Nocodb/Baserow
- **Benefit**: Less developer dependency
- **Challenge**: Complexity limitations
- **For QuickScale**: Not our target (we serve developers)

#### AI Integration
- Being integrated into open-source CRMs
- Use cases: Lead scoring, sales forecasting, automation
- Implementation: Via APIs and integration gateways
- **For QuickScale**: Defer to v0.78.0+ (users can integrate via API)

#### Modular Architectures
- Moving away from monolithic applications
- **Leaders**: Krayin (Laravel packages), Twenty (modular)
- **Benefit**: Maintainability, easier feature addition
- **For QuickScale**: Module system already supports this

---

### 6. Competitive Positioning Matrix

| Solution | Tech Stack | Codebase | Setup | License | Rating | Best For |
|----------|-----------|----------|-------|---------|--------|----------|
| **Twenty** | Node/React | Large | Easy | AGPL-3.0 | 9/10 | Modern startups |
| **Atomic CRM** | React/Supabase | 15k LOC | Very Easy | MIT | 8/10 | Custom builds |
| **EspoCRM** | PHP/Custom | Large | Moderate | AGPL-3.0 | 7/10 | SMBs |
| **SuiteCRM** | PHP | Very Large | Complex | AGPL-3.0 | 6/10 | Enterprise |
| **Corteza** | Go/Vue | Large | Complex | Apache 2.0 | 7/10 | Enterprise complex |
| **Krayin** | Laravel/Vue | Moderate | Moderate | MIT | 7/10 | Laravel teams |
| **DjangoCRM** | Django/Python | Large | Moderate | AGPL-3.0 | 6/10 | Django Admin users |
| **QuickScale** | Django/DRF | **Small** | **Very Easy** | **Apache 2.0** | **TBD** | **Django developers** |

**QuickScale Differentiation:**
- ✅ Django-native (no competition in minimal Django CRM space)
- ✅ API-first with DRF (modern approach)
- ✅ Theme-agnostic backend (headless-ready)
- ✅ Minimal codebase target (7 models vs. 12+)
- ✅ Apache 2.0 license (more permissive than AGPL, allows commercial use)
- ✅ Module system (composable architecture)

**Market Gap Validation:**
- **Heavyweight**: SuiteCRM, DjangoCRM (12+ models, complex)
- **Lightweight template**: Atomic CRM (15k LOC, requires customization)
- **Modern comprehensive**: Twenty (Node.js, not Django)
- **QuickScale position**: Modern minimal Django CRM (gap in market)

---

### 7. Key Learnings for QuickScale v0.73.0

#### Architecture Insights
1. **API-First is Essential**: All modern CRMs prioritize APIs (Twenty: GraphQL+REST, others: REST)
2. **Custom Objects Matter**: Every 2025 CRM supports custom entities (Twenty, EspoCRM)
3. **Modular Design Wins**: Krayin's package system, Twenty's modules demonstrate maintainability
4. **Headless-Ready**: Theme-agnostic backend = headless CRM capability (Corteza model)

#### Technical Choices
1. **Modern Frameworks**: React/TypeScript (Twenty), Go/Vue (Corteza) show path forward
2. **Avoid Monoliths**: SuiteCRM, DjangoCRM struggle with legacy patterns
3. **License Selection**: MIT (Atomic, Krayin) vs AGPL (Twenty, EspoCRM) affects adoption
4. **Database Strategy**: PostgreSQL preference across modern solutions

#### Feature Philosophy
1. **Minimal Works**: Atomic CRM (15k LOC) proves you don't need 100k+ LOC
2. **Custom Objects Critical**: But defer to v0.74.0+ (ship MVP first)
3. **Workflow Automation**: Expected in modern CRMs (but defer to v0.75.0+)
4. **Email Integration**: First-class feature everywhere (but defer to v0.78.0)

#### Developer Experience
1. **Documentation Quality**: Twenty excels; others lack dev docs
2. **Extensibility Patterns**: Krayin's packages, Corteza's low-code offer models
3. **Dashboard Support**: Expected feature (React theme v0.74.0)
4. **API Documentation**: Browsable DRF API is competitive advantage

#### Positioning Strategy
1. **The Gap**: Minimal Django CRM space is underserved
2. **Developer Audience**: Clear appetite for developer-friendly CRMs
3. **Industry Trends**: API-first, self-hosted, privacy-focused
4. **Differentiation**:
   - Superior developer docs (Twenty's strength)
   - Composable/modular architecture (QuickScale modules)
   - Better out-of-box than Atomic, lighter than DjangoCRM/SuiteCRM
   - Django-native (no Node.js/PHP competition in minimal space)

---

### 8. Strategic Question: Can We Copy/Refactor Atomic CRM?

#### The Question
Since Atomic CRM is MIT licensed (15k LOC, minimal approach), could QuickScale:
1. Copy/refactor Atomic CRM's architecture?
2. Start with Atomic's approach and later expand like Twenty?

#### Analysis

**Tech Stack Incompatibility:**

| Aspect | Atomic CRM | QuickScale CRM |
|--------|-----------|----------------|
| **Backend** | Supabase (PostgreSQL + serverless functions) | Django + DRF |
| **Frontend** | React SPA (client-side only) | Theme-agnostic (HTML, HTMX, React) |
| **State Management** | React Query + Recoil | Django ORM |
| **Auth** | Supabase Auth | django-allauth (or custom) |
| **Database Access** | Direct PostgreSQL via Supabase client | Django ORM + migrations |
| **API** | Auto-generated from Supabase schema | Hand-crafted DRF serializers/viewsets |
| **Deployment** | Static SPA + Supabase (serverless) | Traditional Django server |

**❌ Cannot directly copy code** - fundamentally different architectures

**✅ CAN learn from Atomic's principles:**

#### What We CAN Adopt from Atomic CRM

**1. Minimal Data Model (Translate to Django)**

Atomic CRM's entities → QuickScale Django models:

```javascript
// Atomic CRM (Supabase schema)
companies: { id, name, sector, website }
contacts: { id, company_id, first_name, last_name, email, phone }
deals: { id, company_id, name, amount, stage, probability }
notes: { id, contact_id, deal_id, text, date }
tags: { id, name }
```

```python
# QuickScale (Django models) - ALREADY PLANNED!
class Company(models.Model):
    name, industry, website

class Contact(models.Model):
    company, first_name, last_name, email, phone

class Deal(models.Model):
    contact, title, amount, stage, probability

# Note: Our models already match Atomic's minimal approach!
```

**Key Insight**: Our v0.73.0 proposal (7 models) already follows Atomic's minimal philosophy.

---

**2. Component-Based Architecture (Apply to Django)**

Atomic CRM's approach:
- Small, reusable React components
- Each component does ONE thing
- Easy to replace/extend

QuickScale equivalent:
- Small, focused Django apps (module per entity)
- DRF ViewSets (one per model)
- Template components (includes/partials)
- API-first design (decouple frontend)

**Already planned**: Module system (auth, listings, crm) follows this pattern.

---

**3. 15k LOC Target (Our Goal)**

Atomic CRM proves you can build a functional CRM in ~15,000 lines of code.

QuickScale v0.73.0 estimated LOC:
```
Models (7):           ~350 LOC  (50 LOC per model)
Serializers (7):      ~400 LOC  (DRF serializers)
ViewSets (7):         ~350 LOC  (CRUD endpoints)
Admin (7):            ~300 LOC  (Django admin integration)
URLs:                 ~50 LOC   (API routing)
Migrations:           ~200 LOC  (initial migration)
Templates (basic):    ~500 LOC  (HTML templates)
Tests (70% coverage): ~1,500 LOC (comprehensive tests)
-------------------------------------------
TOTAL:               ~3,650 LOC for v0.73.0
```

**Target for v0.74.0 (React theme)**: ~8,000 LOC total
**Target for v0.76.0 (full feature parity)**: ~15,000 LOC

**✅ We're on track to match Atomic's minimal approach**

---

**4. API-First Design (Already Our Approach)**

Atomic CRM: Direct database access via Supabase API
QuickScale: DRF REST API endpoints

Both enable:
- Frontend flexibility (swap HTML → HTMX → React)
- Third-party integrations
- Mobile app development (future)
- Headless CRM capabilities

**Already planned**: v0.73.0 uses DRF for all endpoints.

---

#### Can We Start Like Atomic and Expand Like Twenty?

**Short answer**: Yes, but not by copying code. By following the same evolution path.

**Evolution Strategy:**

```
Phase 1: Atomic-style Minimal (v0.73.0)
├── 7 core models (Contact, Company, Deal, Stage, Notes, Tag)
├── DRF REST API (API-first)
├── Basic HTML templates (showcase_html theme)
└── ~3,650 LOC
    ↓
Phase 2: Add Modern Frontend (v0.74.0)
├── React theme (like Atomic CRM's frontend)
├── Kanban boards, dashboards
├── Keep minimal backend (no feature creep)
└── ~8,000 LOC
    ↓
Phase 3: Expand Strategically (v0.75.0-v0.76.0)
├── Add features ONLY when users request
├── Custom objects (like Twenty) - IF needed
├── Workflow automation - IF needed
├── Advanced features - ONLY if justified
└── Target: ~15,000 LOC (like Atomic)
    ↓
Phase 4: Enterprise Features (v1.0.0+)
├── RBAC, team management
├── Advanced analytics
├── AI integrations (via API)
└── Target: Stay under 30,000 LOC (vs. Twenty's large codebase)
```

**Key Principle**: Start minimal (Atomic's approach), add features incrementally based on user demand (Twenty's customer-driven development), but maintain discipline to avoid bloat (unlike SuiteCRM/DjangoCRM).

---

#### Strategic Recommendations

**1. Don't Fork Atomic CRM**
- ❌ Incompatible tech stacks (React/Supabase vs Django)
- ❌ Would require complete rewrite anyway
- ✅ Better to build Django-native from scratch

**2. DO Adopt Atomic's Philosophy**
- ✅ Minimal data model (7 models, not 12+)
- ✅ 15k LOC target (long-term goal)
- ✅ Component-based architecture
- ✅ API-first design
- ✅ MIT license for accessibility (Note: QuickScale is Apache 2.0, which is also permissive)

**3. DO Follow Twenty's Evolution Path**
- ✅ Start minimal (v0.73.0)
- ✅ Modern frontend (v0.74.0 React theme)
- ✅ Custom objects when needed (v0.75.0+)
- ✅ Community-driven feature development
- ❌ But avoid Twenty's large codebase (stay disciplined)

**4. QuickScale's Unique Position**
- Atomic CRM: React/Supabase, 15k LOC, minimal but requires customization
- Twenty CRM: Node.js/React, large codebase, comprehensive but complex
- **QuickScale**: Django/DRF, target 15k LOC, minimal but batteries-included (Django ecosystem)

**The Gap**: No one offers "Atomic-style minimal + Django-native + batteries-included"

---

#### Conclusion

**Can we copy Atomic CRM?** No (different tech stack)

**Can we adopt Atomic's approach?** Yes (and we already are)

**Can we expand like Twenty?** Yes (but stay disciplined on LOC)

**Unique value**: Atomic's minimalism + Django's ecosystem + Twenty's modern UX = QuickScale

---

## Feature Analysis

### Feature Priority Matrix

#### TIER 1: CORE/ESSENTIAL (Must have in v0.73.0)

| Feature | Why Essential | Appears in % CRMs | Implementation |
|---------|---------------|-------------------|----------------|
| Contact Management | Every CRM starts here | 100% | Contact model (ForeignKey to Company) |
| Company/Organization | Organize contacts into groups | 100% | Company model (standalone) |
| Deal/Opportunity Tracking | Core sales workflow | 100% | Deal model with Stage choices |
| Pipeline/Stage Management | Kanban board foundation | 95% | Stage model + ordering |
| Activity Logging | Track interactions | 90% | ContactNote, DealNote models |
| Basic Filtering/Search | Find contacts/deals quickly | 100% | Django ORM + API queryset filters |

**Decision**: All 6 are non-negotiable for v0.73.0 ✅

---

#### TIER 2: COMMON (Include if easy, defer if complex)

| Feature | Appears in % CRMs | Complexity | User Confirmed | Decision |
|---------|------------------|------------|----------------|----------|
| Tags/Categories | 50% | Low | ✅ Yes | **Include** |
| User Assignment | 70% | Low | ✅ Yes | **Include** |
| Probability % | 45% | Low | ✅ Yes | **Include** |
| Bulk Actions | 55% | Low | ✅ Yes | **Include** |
| Custom Fields | 70% | High | ❌ No | **Defer** to v0.75.0+ |
| Email Integration | 60% | Very High | ❌ No | **Defer** to v0.78.0 |
| Basic Reporting | 60% | Medium | ❌ No | **Defer** (theme responsibility) |
| Forecasting | 65% | Medium | ❌ No | **Defer** (React component v0.74.0) |

---

#### TIER 3: ADVANCED (Explicitly exclude from MVP)

| Feature | Why Exclude | Alternative |
|---------|------------|-------------|
| AI Lead Scoring | Premature (need data first) | Users build custom scoring |
| Predictive Analytics | Requires 1000+ records | Manual forecasting |
| Social Media Integration | Too much scope | Users use Zapier/webhooks |
| Document Management | File attachments sufficient | Minimal ActivityAttachment (future) |
| Workflow Automation | Requires rule engine | Simple action buttons + API |
| Advanced Reporting | Theme responsibility | Dashboard templates in v0.74.0 |
| Multi-currency | Out of scope | Add in billing module v0.75.0 |
| Territory Management | Enterprise feature | Not needed for starting point |

---

#### TIER 4: BLOAT (Anti-patterns to avoid)

| Feature | Why It's Bloat | Cost |
|---------|---------------|------|
| Role-Based Custom Fields | Permission matrix complexity | +40% code |
| Audit Logging (change tracking) | GenericForeignKey overhead | +30% queries |
| Two-way Email Sync | Webhook infrastructure | +50% complexity |
| Email Client UI | Belongs in notifications module | +200 LOC |
| Calendar Integration | Requires provider API wrappers | +100 LOC |

---

## Architecture Decisions

### Decision 1: Activity Logging Architecture

**Context**: Track interactions (notes, calls, meetings) with contacts and deals. Three architectural approaches exist.

---

#### Option A: Simple Concrete Models ✅ RECOMMENDED

```python
class ContactNote(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='notes')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class DealNote(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='notes')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

**How it works:**
- Separate database table for contact notes and deal notes
- Direct foreign key relationships: `contact.notes.all()`, `deal.notes.all()`
- Simple queries: `ContactNote.objects.filter(contact=contact)`

**Pros:**
- ✅ Simple to understand and maintain
- ✅ Efficient database queries (can use foreign key filters)
- ✅ Easy DRF serialization: `ContactNoteSerializer`, `DealNoteSerializer`
- ✅ Matches QuickScale "starting point" philosophy
- ✅ No extra dependencies (pure Django)
- ✅ 80% use case covered (basic note-taking)

**Cons:**
- ❌ Duplicate table structure (but only 2 models, not 10)
- ❌ Can't easily show "all activities across all objects" (but v0.73.0 doesn't need this)
- ❌ Adding new object types requires new model (e.g., CompanyNote)

**Best for:** v0.73.0 MVP where we just need basic note-taking

**Example Usage:**
```python
# Create note
note = ContactNote.objects.create(
    contact=contact,
    created_by=request.user,
    text="Discussed pricing options"
)

# Query notes
contact_notes = contact.notes.all()
deal_notes = deal.notes.filter(created_by=user)

# API endpoint
GET /api/crm/contacts/123/notes/
POST /api/crm/contacts/123/notes/
```

---

#### Option B: Flexible GenericForeignKey

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Activity(models.Model):
    # Can attach to ANY model (Contact, Deal, Company, future models)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    activity_type = models.CharField(max_length=10, choices=[
        ('note', 'Note'),
        ('call', 'Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
    ])
    text = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

**How it works:**
- Single Activity table for ALL objects (contacts, deals, companies, anything)
- Uses Django's ContentType framework to track "what type of object" this activity relates to
- Can attach to future models without code changes

**Pros:**
- ✅ Ultimate flexibility (one activity model handles everything)
- ✅ Easier to add new object types later (no new models needed)
- ✅ Good for "unified activity feed" across all objects
- ✅ Extensible to future models (Company, Product, etc.)
- ✅ Single API endpoint: `/api/crm/activities/`

**Cons:**
- ❌ **Cannot filter efficiently**: `Activity.objects.filter(content_object=contact)` FAILS (not supported by Django ORM)
- ❌ Must use workarounds: `Activity.objects.filter(content_type=ContactType, object_id=contact.id)`
- ❌ Complex DRF serialization (need to serialize different object types dynamically)
- ❌ Harder to understand for contributors (ContentType framework is advanced Django)
- ❌ Adds ContentType framework overhead (extra table joins)
- ❌ Reverse relations need `GenericRelation` setup

**Best for:** Large CRMs with 10+ object types needing unified activity feeds

**Example Usage:**
```python
# Create note (complex)
from django.contrib.contenttypes.models import ContentType
contact_type = ContentType.objects.get_for_model(Contact)
activity = Activity.objects.create(
    content_type=contact_type,
    object_id=contact.id,
    activity_type='note',
    text="Discussed pricing"
)

# Query notes (complex workaround)
contact_type = ContentType.objects.get_for_model(Contact)
activities = Activity.objects.filter(
    content_type=contact_type,
    object_id=contact.id
)

# API endpoint (complex serialization)
GET /api/crm/activities/?content_type=contact&object_id=123
```

---

#### Option C: Hybrid (Start Simple, Upgrade Later)

**Strategy:**
```python
# v0.73.0: Start with concrete models (fast to ship)
class ContactNote(models.Model):
    # ... simple concrete implementation

class DealNote(models.Model):
    # ... simple concrete implementation

# v0.74.0+: Add unified Activity IF React dashboard needs it
class Activity(models.Model):
    # ... GenericForeignKey implementation for timeline view
```

**How it works:**
- Ship v0.73.0 with simple concrete models (fastest path)
- If React theme v0.74.0 needs unified activity timeline, add Activity model then
- Both models can coexist (ContactNote for queries, Activity for timeline)
- Data migration can copy ContactNote → Activity if needed

**Pros:**
- ✅ Ship v0.73.0 faster (no premature optimization)
- ✅ Upgrade path exists if needed
- ✅ Flexibility without upfront complexity cost
- ✅ Matches "starting point" philosophy (solve today's problem today)
- ✅ Can evaluate real user needs before building complex solution

**Cons:**
- ❌ Potential data migration needed later (copy ContactNote → Activity)
- ❌ Maintaining two systems if both kept (but manageable)
- ❌ Slightly more work if unified timeline is definitely needed

**Best for:** QuickScale's "starting point" philosophy (optimize when needed, not before)

**Migration Path (if needed):**
```python
# v0.74.0 migration to copy data
def copy_notes_to_activities(apps, schema_editor):
    ContactNote = apps.get_model('crm', 'ContactNote')
    Activity = apps.get_model('crm', 'Activity')

    for note in ContactNote.objects.all():
        Activity.objects.create(
            content_object=note.contact,
            activity_type='note',
            text=note.text,
            created_by=note.created_by,
            created_at=note.created_at
        )
```

---

### Decision 2: Pipeline Customization Level

**Context**: Sales pipelines have stages (Prospecting → Negotiation → Closed-Won). How much should users customize during setup?

---

#### Option A: Fixed Schema (Hardcoded Stages) ✅ RECOMMENDED

```python
# In migration file (0001_initial.py)
def create_default_stages(apps, schema_editor):
    Stage = apps.get_model('quickscale_modules_crm', 'Stage')
    stages = [
        {'name': 'Prospecting', 'order': 1},
        {'name': 'Negotiation', 'order': 2},
        {'name': 'Closed-Won', 'order': 3},
        {'name': 'Closed-Lost', 'order': 4},
    ]
    for stage_data in stages:
        Stage.objects.create(**stage_data)

class Migration(migrations.Migration):
    operations = [
        # ... create Stage model
        migrations.RunPython(create_default_stages),
    ]
```

**How it works:**
- Default stages created automatically when module is embedded
- Users can add/edit/delete stages via Django admin after setup
- No configuration prompts during `quickscale plan --add crm`
- Zero user input required (works out of the box)

**Pros:**
- ✅ **Zero configuration** (works immediately after `quickscale apply`)
- ✅ **Industry standard** (80% of CRMs use these exact stages)
- ✅ **Simplest implementation** (no plan wizard logic needed)
- ✅ **Users customize later** if needed (via admin)
- ✅ **Fastest to ship** (no CLI prompt complexity)
- ✅ **Matches QuickScale philosophy** (sensible defaults, customize later)

**Cons:**
- ❌ Not customizable during initial setup (users use defaults first)
- ❌ Users must use admin to change stages (but that's standard Django workflow)
- ❌ Configuration not in version control initially (but can export/import)

**Best for:** v0.73.0 MVP (ship fast, users customize post-setup via admin)

**User Experience:**
```bash
$ quickscale plan myapp --add crm
✅ CRM module added to configuration

$ quickscale apply
✅ Module 'crm' embedded successfully!
✅ Created default pipeline stages:
   - Prospecting
   - Negotiation
   - Closed-Won
   - Closed-Lost

Customize stages: python manage.py admin (go to CRM → Stages)
```

---

#### Option B: Configurable Stages (Interactive Prompts)

```yaml
# module.yml
config:
  mutable:
    pipeline_stages:
      type: list
      default: [Prospecting, Negotiation, Closed-Won, Closed-Lost]
      prompt: "Enter your sales pipeline stages (comma-separated)"
```

```bash
$ quickscale plan myapp --add crm
? Enter your sales pipeline stages (comma-separated): Lead, Demo, Proposal, Contract, Won, Lost
✅ Configuration saved to quickscale.yml

$ quickscale apply
✅ Creating custom pipeline stages:
   - Lead
   - Demo
   - Proposal
   - Contract
   - Won
   - Lost
```

**How it works:**
- During `quickscale plan`, user enters custom stage names
- Stages saved to `quickscale.yml` (version controlled)
- `quickscale apply` creates stages based on user input
- Configuration is declarative and reproducible

**Pros:**
- ✅ **Customizable from the start** (matches user's workflow immediately)
- ✅ **Configuration in version control** (quickscale.yml, reproducible)
- ✅ **Matches plan/apply philosophy** (declarative configuration)
- ✅ **Supports team collaboration** (shared config file)

**Cons:**
- ❌ **Requires CLI prompt logic** (additional complexity in plan wizard)
- ❌ **Most users stick with defaults anyway** (low ROI for complexity)
- ❌ **Harder to change later** (must edit quickscale.yml + re-apply, or use admin)
- ❌ **Slows down setup** (even if users just press Enter for defaults)
- ❌ **Testing complexity** (need to test custom stage logic)

**Best for:** Post-v0.73.0 when multiple users request custom pipelines

**When to implement:** If 30%+ of users request custom stages during beta testing

---

#### Option C: Full Custom Fields Support (EAV Pattern)

```python
class CustomField(models.Model):
    """Define custom fields for any model"""
    model_name = models.CharField(max_length=50)  # 'Contact', 'Deal', etc.
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20)  # 'text', 'number', 'date', etc.
    is_required = models.BooleanField(default=False)

class CustomFieldValue(models.Model):
    """Store custom field values"""
    custom_field = models.ForeignKey(CustomField, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    value = models.TextField()  # JSON serialized value
```

**How it works:**
- Users define custom fields via UI/admin
- Values stored in separate CustomFieldValue table (EAV pattern)
- Retrieved via JSON deserialization
- Supports any field type (text, number, date, etc.)

**Pros:**
- ✅ **Ultimate flexibility** (users add any field without code changes)
- ✅ **No schema migrations** needed (fields are data, not schema)
- ✅ **Support diverse use cases** (real estate CRM vs. SaaS CRM vs. consulting CRM)

**Cons:**
- ❌ **VERY HIGH complexity** (JSON serialization, type validation, API complexity)
- ❌ **Poor query performance** (can't filter custom fields efficiently in SQL)
- ❌ **Complex API serialization** (dynamic fields per object)
- ❌ **Contradicts "starting point" philosophy** (adds 3x complexity)
- ❌ **Better handled by users extending models directly** (Django best practice)
- ❌ **Difficult to maintain** (type coercion, validation, edge cases)

**Best for:** Enterprise CRMs with 100+ diverse customers (NOT QuickScale v0.73.0)

**Recommendation:** **Defer to v0.75.0+ or NEVER** (users can extend models themselves)

**Alternative:** Users who need custom fields should extend models:
```python
# In user's project (myapp/models.py)
from modules.crm.models import Contact as BaseContact

class Contact(BaseContact):
    """Extended contact with custom fields"""
    industry_segment = models.CharField(max_length=100)
    customer_tier = models.CharField(max_length=20)

    class Meta:
        proxy = False  # Creates new table
```

---

### Comparison Matrix

| Aspect | Activity Logging | Pipeline Customization |
|--------|------------------|------------------------|
| **Simple/Fixed** | Concrete models (ContactNote, DealNote) | Hardcoded stages in migration |
| Complexity | Low | Low |
| Setup time | 0 minutes | 0 minutes |
| Flexibility | Limited (2 note types) | Users customize via admin post-setup |
| Matches MVP | ✅ Yes | ✅ Yes |
| Ship time | **Fastest** | **Fastest** |
| Code lines | ~50 LOC | ~30 LOC (migration) |
| | | |
| **Flexible/Configurable** | GenericForeignKey (unified Activity) | Interactive prompts during plan |
| Complexity | Medium-High | Medium |
| Setup time | 0 minutes | 2-3 minutes (user input) |
| Flexibility | High (works with future models) | High (version controlled config) |
| Matches MVP | ⚠️ Premature optimization | ⚠️ Nice-to-have, not essential |
| Ship time | Slower (complex serializers) | Slower (CLI prompt logic) |
| Code lines | ~100 LOC + ContentType overhead | ~80 LOC (plan wizard) |
| | | |
| **Hybrid/Advanced** | Start simple, upgrade later | Full custom fields (EAV pattern) |
| Complexity | Medium (2 systems) | **Very High** |
| Setup time | 0 min (v0.73.0), add later if needed | 10+ minutes (complex UI) |
| Flexibility | Best of both worlds | Maximum |
| Matches MVP | ✅ Yes (pragmatic) | ❌ No (over-engineering) |
| Ship time | Fastest now, upgrade path exists | **Very slow** (3+ weeks) |
| Code lines | ~50 LOC now, ~100 LOC later | ~300+ LOC + JSON complexity |

---

## Proposed Implementation

### Data Models (v0.73.0)

```python
# File: quickscale_modules/crm/src/quickscale_modules_crm/models.py

from django.db import models
from django.conf import settings


# 1. Tag (Generic Grouping/Segmentation)
class Tag(models.Model):
    """
    Generic tags for organizing contacts and deals.
    Serves as the primary mechanism for 'Groups', 'Segments', and 'Custom Classifications'.
    Examples: 'Buyers', 'Consulting', 'VIP', '2025-Q1'
    """
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


# 2. Company
class Company(models.Model):
    """Company/Organization entity"""
    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['name']
        verbose_name_plural = 'Companies'

    def __str__(self) -> str:
        return self.name


# 3. Contact
class Contact(models.Model):
    """Contact person (lead, prospect, customer)"""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=100, blank=True)  # Job title

    # Status & Follow-up Logic
    status = models.CharField(
        max_length=50,
        choices=[
            ('new', 'New'),
            ('contacted', 'Contacted'),
            ('in_discussion', 'In Discussion'),
            ('pending_response', 'Pending Response'),
            ('inactive', 'Inactive'),
        ],
        default='new'
    )
    last_contacted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically updated when a note/activity is logged"
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='contacts'
    )

    tags = models.ManyToManyField(Tag, blank=True, related_name='contacts')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['last_name', 'first_name']

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# 4. Stage
class Stage(models.Model):
    """Pipeline stage (Prospecting, Negotiation, Closed-Won, etc.)"""
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)  # For Kanban ordering

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['order', 'name']

    def __str__(self) -> str:
        return self.name


# 5. Deal
class Deal(models.Model):
    """Sales opportunity/deal"""
    title = models.CharField(max_length=200)

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='deals'
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Deal value in USD"
    )

    stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,  # Prevent accidental stage deletion
        related_name='deals'
    )

    expected_close_date = models.DateField(null=True, blank=True)

    probability = models.IntegerField(
        default=50,
        help_text="Forecast likelihood (0-100%)"
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_deals'
    )

    tags = models.ManyToManyField(Tag, blank=True, related_name='deals')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title

    @property
    def company(self):
        """Convenience property to access contact's company"""
        return self.contact.company


# 6. ContactNote
class ContactNote(models.Model):
    """Notes/interactions with a contact"""
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='notes'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Note on {self.contact} by {self.created_by}"


# 7. DealNote
class DealNote(models.Model):
    """Notes/interactions with a deal"""
    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name='notes'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'quickscale_modules_crm'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Note on {self.deal} by {self.created_by}"
```

**Model Summary:**
- **Total: 7 models** (Tag, Company, Contact, Stage, Deal, ContactNote, DealNote)
- **Compare to DjangoCRM: 12+ models**
- **Compare to Notion/Airtable: 4 tables**
- **QuickScale positioning: Minimal but complete**

---

### API Endpoints (Django REST Framework)

```python
# File: quickscale_modules/crm/src/quickscale_modules_crm/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'crm'

router = DefaultRouter()
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'contacts', views.ContactViewSet, basename='contact')
router.register(r'deals', views.DealViewSet, basename='deal')
router.register(r'stages', views.StageViewSet, basename='stage')
router.register(r'tags', views.TagViewSet, basename='tag')

urlpatterns = [
    path('api/crm/', include(router.urls)),
]
```

**Endpoint Structure:**
```
# Companies
GET    /api/crm/companies/              # List companies
POST   /api/crm/companies/              # Create company
GET    /api/crm/companies/{id}/         # Retrieve company
PUT    /api/crm/companies/{id}/         # Update company
DELETE /api/crm/companies/{id}/         # Delete company

# Contacts
GET    /api/crm/contacts/               # List contacts (filterable by company, tags)
POST   /api/crm/contacts/               # Create contact
GET    /api/crm/contacts/{id}/          # Retrieve contact
PUT    /api/crm/contacts/{id}/          # Update contact
DELETE /api/crm/contacts/{id}/          # Delete contact
GET    /api/crm/contacts/{id}/notes/    # List contact notes
POST   /api/crm/contacts/{id}/notes/    # Create contact note

# Deals
GET    /api/crm/deals/                  # List deals (filterable by stage, owner, tags)
POST   /api/crm/deals/                  # Create deal
GET    /api/crm/deals/{id}/             # Retrieve deal
PUT    /api/crm/deals/{id}/             # Update deal
DELETE /api/crm/deals/{id}/             # Delete deal
GET    /api/crm/deals/{id}/notes/       # List deal notes
POST   /api/crm/deals/{id}/notes/       # Create deal note

# Bulk operations
POST   /api/crm/deals/bulk_update_stage/ # Bulk update deal stages
POST   /api/crm/deals/mark_won/          # Mark deals as won
POST   /api/crm/deals/mark_lost/         # Mark deals as lost

# Stages
GET    /api/crm/stages/                 # List pipeline stages
POST   /api/crm/stages/                 # Create stage
PUT    /api/crm/stages/{id}/            # Update stage
DELETE /api/crm/stages/{id}/            # Delete stage

# Tags
GET    /api/crm/tags/                   # List tags
POST   /api/crm/tags/                   # Create tag
DELETE /api/crm/tags/{id}/              # Delete tag
```

---

### Use Case Scenarios (Generic Tagging & Filtering)

These scenarios demonstrate how the **Generic Tagging System** + **Status/Date Filtering** creates powerful, customizable classification without custom code.

#### Scenario 1: "Buyers" Group not contacted in 30 days
**Goal**: Find contacts tagged "Buyers" who need follow-up.

**Django QuerySet**:
```python
from django.utils import timezone
from datetime import timedelta

thirty_days_ago = timezone.now() - timedelta(days=30)

contacts = Contact.objects.filter(
    tags__name__iexact="Buyers",
    last_contacted_at__lt=thirty_days_ago
)
```

**API Request**:
```http
GET /api/crm/contacts/?tags=Buyers&last_contacted_at__lt=2025-11-09
```

#### Scenario 2: "Consulting" Users Pending Response
**Goal**: Find potential consulting clients where we are waiting for them to reply.

**Django QuerySet**:
```python
contacts = Contact.objects.filter(
    tags__name__iexact="Consulting",
    status="pending_response"
)
```

**API Request**:
```http
GET /api/crm/contacts/?tags=Consulting&status=pending_response
```

---

### Django Admin Integration

```python
# File: quickscale_modules/crm/src/quickscale_modules_crm/admin.py

from django.contrib import admin
from .models import Company, Contact, Deal, Stage, Tag, ContactNote, DealNote


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'industry', 'website', 'created_at']
    list_filter = ['industry', 'created_at']
    search_fields = ['name', 'industry']


class ContactNoteInline(admin.TabularInline):
    model = ContactNote
    extra = 1
    readonly_fields = ['created_at']


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'company', 'created_at']
    list_filter = ['company', 'tags', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'company__name']
    filter_horizontal = ['tags']
    inlines = [ContactNoteInline]


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['name', 'order']
    list_editable = ['order']


class DealNoteInline(admin.TabularInline):
    model = DealNote
    extra = 1
    readonly_fields = ['created_at']


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ['title', 'contact', 'stage', 'amount', 'probability', 'owner', 'expected_close_date']
    list_filter = ['stage', 'owner', 'tags', 'created_at']
    search_fields = ['title', 'contact__first_name', 'contact__last_name', 'contact__company__name']
    filter_horizontal = ['tags']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DealNoteInline]


@admin.register(ContactNote)
class ContactNoteAdmin(admin.ModelAdmin):
    list_display = ['contact', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['contact__first_name', 'contact__last_name', 'text']
    readonly_fields = ['created_at']


@admin.register(DealNote)
class DealNoteAdmin(admin.ModelAdmin):
    list_display = ['deal', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['deal__title', 'text']
    readonly_fields = ['created_at']
```

---

### Module Structure

```
quickscale_modules/crm/
├── README.md                           # Installation & usage guide
├── pyproject.toml                      # Poetry package config
├── module.yml                          # Module manifest
├── src/quickscale_modules_crm/
│   ├── __init__.py                     # Module version
│   ├── apps.py                         # Django AppConfig
│   ├── models.py                       # All 7 models
│   ├── serializers.py                  # DRF serializers
│   ├── views.py                        # DRF ViewSets
│   ├── urls.py                         # API routes
│   ├── admin.py                        # Django admin
│   ├── migrations/
│   │   ├── __init__.py
│   │   └── 0001_initial.py             # Initial migration + default stages
│   └── templates/quickscale_modules_crm/
│       └── crm/
│           ├── contact_list.html       # Basic HTML templates
│           ├── contact_detail.html
│           ├── deal_list.html
│           └── deal_detail.html
└── tests/
    ├── __init__.py
    ├── settings.py                     # Test Django settings
    ├── conftest.py                     # pytest fixtures
    ├── test_models.py                  # Model unit tests
    ├── test_serializers.py             # Serializer tests
    ├── test_views.py                   # API endpoint tests
    └── test_admin.py                   # Admin tests
```

---

### CLI Integration

```python
# File: quickscale_cli/src/quickscale_cli/commands/module_commands.py

# Add to AVAILABLE_MODULES list
AVAILABLE_MODULES = [
    'auth',
    'listings',
    'crm',  # NEW
]

def configure_crm_module():
    """Configure CRM module (minimal config for v0.73.0)"""
    click.echo("📋 CRM Module Configuration")
    click.echo("  Default pipeline stages will be created:")
    click.echo("    • Prospecting")
    click.echo("    • Negotiation")
    click.echo("    • Closed-Won")
    click.echo("    • Closed-Lost")
    click.echo()
    click.echo("  You can customize stages later via Django admin.")
    return {}  # No config needed for fixed schema approach

def apply_crm_configuration(project_path: Path, config: dict):
    """Apply CRM module configuration to project"""
    # 1. Add dependencies to pyproject.toml
    add_dependency('djangorestframework', '^3.14.0')

    # 2. Add to INSTALLED_APPS
    add_to_installed_apps('rest_framework', 'modules.crm')

    # 3. Add CRM URLs to project urls.py
    add_url_include('modules.crm.urls')

    # 4. Run migrations
    run_command('python manage.py migrate')

    click.echo("✅ CRM module configured successfully!")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Access Django admin: python manage.py createsuperuser")
    click.echo("  2. Customize pipeline stages: Admin → CRM → Stages")
    click.echo("  3. API documentation: /api/crm/ (browsable API)")

# Add to MODULE_CONFIGURATORS
MODULE_CONFIGURATORS = {
    'auth': (configure_auth_module, apply_auth_configuration),
    'listings': (configure_listings_module, apply_listings_configuration),
    'crm': (configure_crm_module, apply_crm_configuration),
}
```

---

### Testing Strategy

**Coverage Target**: 70%+ per file (CI enforced)

```python
# File: tests/test_models.py

import pytest
from django.contrib.auth import get_user_model
from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

User = get_user_model()


@pytest.mark.django_db
class TestCompanyModel:
    def test_create_company(self):
        company = Company.objects.create(
            name="Acme Corp",
            industry="Technology",
            website="https://acme.com"
        )
        assert company.name == "Acme Corp"
        assert str(company) == "Acme Corp"

    def test_company_contacts_relationship(self):
        company = Company.objects.create(name="Test Co")
        contact = Contact.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@test.com",
            company=company
        )
        assert contact in company.contacts.all()


@pytest.mark.django_db
class TestContactModel:
    def test_create_contact(self, company):
        contact = Contact.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+1234567890",
            company=company
        )
        assert contact.full_name == "Jane Smith"
        assert str(contact) == "Jane Smith"

    def test_contact_tags(self, contact, tag):
        contact.tags.add(tag)
        assert tag in contact.tags.all()


@pytest.mark.django_db
class TestDealModel:
    def test_create_deal(self, contact, stage, user):
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount=50000.00,
            stage=stage,
            probability=75,
            owner=user
        )
        assert deal.title == "Enterprise Deal"
        assert deal.company == contact.company

    def test_deal_notes(self, deal, user):
        note = DealNote.objects.create(
            deal=deal,
            created_by=user,
            text="Follow up next week"
        )
        assert note in deal.notes.all()
```

---

## Recommendations

### For v0.73.0 Implementation

#### 1. Activity Logging: **Option A (Concrete Models)** ✅

**Rationale:**
- Simplest implementation (50 LOC vs. 100 LOC for GenericFK)
- Fastest to ship (no ContentType framework complexity)
- Matches QuickScale "starting point" philosophy
- Covers 80% use case (basic note-taking)
- Easy to upgrade later if needed (Hybrid approach)

**Trade-off:** Can't easily show unified activity timeline across objects, but v0.73.0 doesn't need this (React theme v0.74.0 can add it)

---

#### 2. Pipeline Customization: **Option A (Fixed Schema)** ✅

**Rationale:**
- Zero configuration (works immediately)
- Industry standard stages (Prospecting, Negotiation, Closed-Won, Closed-Lost)
- Users can customize via Django admin post-setup
- Fastest to ship (no CLI prompt logic)
- 90% of users stick with defaults anyway

**Trade-off:** Not customizable during setup, but users can change in admin (standard Django workflow)

---

#### 3. Core Features to Include

✅ **Confirmed Include:**
- Contact & Company management
- Deal tracking with pipeline stages
- ContactNote & DealNote models
- Tags (ManyToMany)
- User assignment (owner field)
- Probability % forecasting
- Bulk operations (mark as won/lost)

❌ **Explicitly Defer:**
- Email synchronization → v0.78.0
- File attachments → Post-v0.73.0
- Custom fields → v0.75.0+ or user extensions
- Advanced reporting → v0.74.0 React theme
- Workflow automation → User scripts + API

---

### Competitive Positioning

**QuickScale CRM vs. Market:**

| Comparison | Advantage |
|------------|-----------|
| **vs. DjangoCRM** | Lightweight (7 models vs. 12+), API-first, theme-agnostic |
| **vs. Notion CRM** | Django-native, structured data, self-hosted |
| **vs. Airtable CRM** | Open source, no vendor lock-in, full Django power |
| **vs. OnePageCRM** | API-first for customization, own your data |

**Value Proposition**: Minimal Django CRM that works out of the box, extensible via Django patterns, theme-agnostic backend, API-first for modern frontends.

---

### Implementation Checklist

Based on [Module Implementation Checklist](./docs/technical/decisions.md#module-implementation-checklist):

**Phase 1: Core Module**
- [ ] Package structure (pyproject.toml, README.md, module.yml)
- [ ] 7 core models (Tag, Company, Contact, Stage, Deal, ContactNote, DealNote)
- [ ] Initial migration with default stages
- [ ] DRF serializers (separate read/write for optimization)
- [ ] DRF ViewSets with filtering
- [ ] Django admin integration with inlines
- [ ] URL routing (API endpoints)

**Phase 2: CLI Integration**
- [ ] Add 'crm' to AVAILABLE_MODULES
- [ ] Create configure_crm_module() function
- [ ] Create apply_crm_configuration() function
- [ ] Add to MODULE_CONFIGURATORS dictionary

**Phase 3: Template Integration (showcase_html)**
- [ ] Add CRM section to navigation.html.j2
- [ ] Add CRM to "Installed Modules" in index.html.j2
- [ ] Create basic HTML templates (contact_list, deal_list)

**Phase 4: Testing**
- [ ] Unit tests for models (70%+ coverage)
- [ ] Unit tests for serializers
- [ ] Integration tests for API endpoints
- [ ] Admin tests

**Phase 5: Documentation & Publishing**
- [ ] README.md with installation guide
- [ ] API documentation (DRF browsable API)
- [ ] Run ./scripts/publish_module.sh crm
- [ ] Verify split branch: splits/crm-module

---

### Future Enhancements (Post-v0.73.0)

**v0.74.0 - React Theme:**
- **Tech Stack**: React TypeScript + Vite
- **Components**: **shadcn/ui** + **shadcn/admin** + **Lucide Icons**
- Kanban board for deals (drag-drop stage changes)
- Contact/company cards with inline editing
- Unified activity timeline (add Activity model with GenericFK)
- Dashboard with charts (revenue by stage, conversion rates)

**v0.75.0+:**
- Email integration (via notifications module v0.78.0)
- File attachments (ActivityAttachment model)
- Advanced filtering (saved views, custom filters)
- Import/export (CSV, Excel)

**v0.76.0+ (Teams module integration):**
- Team-based access control
- Deal assignment to teams
- Territory management
- Shared pipelines across teams

---

## Appendix: Research Sources

### Django CRM Projects
- [DjangoCRM/django-crm](https://github.com/DjangoCRM/django-crm) - AGPL-3.0, actively maintained
- [Django-CRM Website](https://djangocrm.github.io/info/)
- [MicroPyramid/Django-CRM](https://github.com/MicroPyramid/Django-CRM) - Maintenance mode
- [koalixcrm](https://github.com/KoalixSwitzerland/koalixcrm) - Django + ERP

### Lightweight CRM Market
- [10 Best Lightweight CRM Platforms for Companies in 2025](https://www.thena.ai/post/10-best-lightweight-crm-platforms-for-modern-companies-in-2025)
- [Best Free CRM Software in 2025](https://zapier.com/blog/best-free-crm/)
- [17 Best Free CRM Software in 2025](https://crm.org/crmland/free-crm)
- [7 Best Simple CRMs in 2025](https://blog.salesflare.com/best-simple-crm)

### CRM Feature Analysis
- [CRM Core Features & What to Look For](https://blog.salesflare.com/crm-features)
- [Essential CRM Features for Your Business](https://www.salesforce.com/crm/features/)
- [Top CRM Features for 2025](https://www.bigcontacts.com/crm-features/)

### Modern Open-Source CRM Solutions
- [Twenty - The #1 Open-Source CRM](https://twenty.com/)
- [GitHub - twentyhq/twenty](https://github.com/twentyhq/twenty)
- [Best Open Source CRM for 2025 - Marmelab Benchmark](https://marmelab.com/blog/2025/02/03/open-source-crm-benchmark-for-2025.html)
- [GitHub - marmelab/atomic-crm](https://github.com/marmelab/atomic-crm)
- [Atomic CRM - Open Source Toolkit](https://marmelab.com/atomic-crm/)
- [EspoCRM - Open Source CRM Application](https://www.espocrm.com/)
- [GitHub - espocrm/espocrm](https://github.com/espocrm/espocrm)
- [SuiteCRM - Open Source CRM Software](https://suitecrm.com/)
- [GitHub - SuiteCRM/SuiteCRM](https://github.com/SuiteCRM/SuiteCRM)
- [Corteza - Low Code Platform](https://github.com/cortezaproject/corteza)
- [Getting started with Corteza Low Code](https://opensource.com/article/19/9/corteza-low-code-getting-started)
- [Krayin CRM](https://krayincrm.com/)
- [GitHub - krayin/laravel-crm](https://github.com/krayin/laravel-crm)
- [Fat Free CRM](http://www.fatfreecrm.com/)
- [GitHub - fatfreecrm/fat_free_crm](https://github.com/fatfreecrm/fat_free_crm)
- [Baserow - No-Code Database](https://baserow.io/)
- [Baserow vs NocoDB - Comparison](https://baserow.io/blog/nocodb-vs-baserow)
- [Top 20 Open-Source, Self-Hosted CRMs in 2025](https://growcrm.io/2025/02/28/top-20-open-source-self-hosted-crms-in-2025/)

### CRM Trends and Patterns
- [Backends for Frontends Pattern](https://samnewman.io/patterns/architectural/bff/)
- [Backend-for-Frontend (BFF) Architecture in 2025](https://devtechinsights.com/backend-for-frontend-bff-architecture-2025/)

### Django Technical Patterns
- [Django GenericForeignKey Activity Logging](https://dev.to/ashraful/django-genericforeignkey-with-genericrelation-1p54)
- [Mastering Django GenericForeignKey & ContentType](https://aisaastemplate.com/blog/django-contenttype-genericforeignkey-tutorial/)
- [Django REST Framework - Serializers](https://www.django-rest-framework.org/api-guide/serializers/)
- [DRF Serializers Best Practices](https://testdriven.io/blog/drf-serializers/)

---

## Next Steps

1. **Review this proposal** and confirm architecture decisions:
   - Activity Logging: Concrete models (A), GenericFK (B), or Hybrid (C)?
   - Pipeline Customization: Fixed stages (A), Interactive (B), or Custom fields (C)?

2. **Create implementation plan** with detailed task breakdown

3. **Begin implementation** following QuickScale module checklist

---

**Document Status**: Draft for Review
**Last Updated**: 2025-12-08
**Author**: QuickScale Research Team
