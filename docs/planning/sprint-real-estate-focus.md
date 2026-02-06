# Sprint Plan: Real Estate Agency Focus (v0.75.0 - v0.77.0)

## Sprint Goal
Prioritize and complete modules essential for building a production-ready Real Estate Agency website using QuickScale with React frontend.

## Context
User needs to create a Real Estate Agency web page using QuickScale. The sprint plan prioritizes modules and features that directly support this use case, with React as the default frontend (v0.74.0 complete).

## Duration
Estimated: 8-12 weeks (based on module complexity and dependencies)

## Current State (v0.74.0)

**✅ Completed:**
- React Default Theme (showcase_react) with shadcn/ui
- Auth Module (v0.63.0) - django-allauth integration
- Listings Module (v0.67.0) - generic base for vertical themes
- CRM Module (v0.73.0) - API-only backend
- Plan/Apply System (v0.68.0-v0.71.0) - Terraform-style configuration

**📋 Next Release:** v0.75.0 - CRM Theme (React frontend)

## Real Estate Agency Requirements Analysis

### Essential Modules for Real Estate:

1. **Listings Module** ✅ (v0.67.0 - Complete)
   - Property listings (houses, apartments, commercial)
   - Search and filtering capabilities
   - Image galleries and virtual tours
   - Location-based features

2. **CRM Module** ✅ (v0.73.0 - API Complete) + 🚧 (v0.75.0 - Frontend Needed)
   - Contact management (buyers, sellers, agents)
   - Deal pipeline (inquiry → viewing → offer → closed)
   - Lead tracking and follow-ups
   - Communication history

3. **Auth Module** ✅ (v0.63.0 - Complete)
   - User registration (buyers, sellers, agents)
   - Profile management
   - Authentication flows

4. **Billing Module** 📋 (v0.76.0 - Planned)
   - Premium listings for sellers
   - Featured properties
   - Agent subscriptions
   - Payment processing

5. **Teams Module** 📋 (v0.77.0 - Planned)
   - Agency/brokerage management
   - Agent roles and permissions
   - Team-based property assignments

### Lower Priority (Post Real Estate Agency):
- Notifications (v0.79.0) - email updates for new listings
- HTMX theme (v0.78.0+) - alternative frontend option

---

## Selected Tasks (Prioritized for Real Estate)

| Priority | Release | Module | Effort | Status | Real Estate Value |
|----------|---------|--------|--------|--------|-------------------|
| **P0** | v0.75.0 | CRM Theme (React) | 7d | 📋 Planned | **CRITICAL** - Contact mgmt, deal pipeline for buyers/sellers |
| **P1** | v0.76.0 | Billing Module | 10d | 📋 Planned | **HIGH** - Premium listings, featured properties revenue |
| **P1** | v0.77.0 | Teams Module | 8d | 📋 Planned | **HIGH** - Agency/brokerage multi-agent support |
| **P2** | v0.78.0+ | HTMX Theme | 5d | 📋 Deferred | **MEDIUM** - Alternative frontend option |
| **P2** | v0.79.0 | Notifications | 6d | 📋 Deferred | **MEDIUM** - New listing alerts, inquiry notifications |

---

## Priority 0 (P0): CRM Theme - v0.75.0

**Why P0 for Real Estate:**
- Contact management is CORE to real estate (buyers, sellers, agents)
- Deal pipeline tracks property inquiries through to closing
- CRM backend is complete (v0.73.0), needs React frontend only
- Complements existing Listings module perfectly

**Implementation Tasks:**

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| T1 | CRM Dashboard Page (React) | 1.5d | showcase_react (v0.74.0) |
| T2 | Kanban Board Component (Deal Pipeline) | 2d | T1, TanStack Query |
| T3 | Contact List & Detail Views | 1.5d | T1, shadcn/ui Table |
| T4 | Company Management Views | 1d | T3 |
| T5 | Deal Detail with Notes (inline editing) | 1.5d | T2, React Hook Form |
| T6 | CRM Metrics & Analytics Dashboard | 1d | T1, Recharts |
| T7 | Integration Testing & E2E | 0.5d | All above |

**Total Effort:** ~7 days

**Real Estate Use Cases:**
- Track buyer inquiries and viewing schedules
- Manage seller contacts and property listings
- Visualize deal stages (inquiry → viewing → offer → closed)
- Associate deals with specific properties
- Agent activity tracking

**Success Criteria:**
- [x] Kanban board shows deals by stage (drag-and-drop)
- [x] Contact list with search/filter by buyer/seller/agent
- [x] Deal detail view with property association
- [x] Live API integration with CRM backend (v0.73.0)
- [x] Mobile-responsive design (shadcn/ui)

---

## Priority 1 (P1): Billing Module - v0.76.0

**Why P1 for Real Estate:**
- Monetization: Premium/featured listings for sellers
- Agent subscriptions: Tiered plans (free, basic, premium)
- Revenue stream essential for agency business model

**Implementation Tasks:**

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| T1 | Stripe Integration (dj-stripe setup) | 1.5d | None |
| T2 | Subscription Models & Admin | 1.5d | T1 |
| T3 | Pricing Tier Management | 1d | T2 |
| T4 | Payment Method Handling | 1d | T1 |
| T5 | Webhook Processing | 1.5d | T1, T2 |
| T6 | Billing Dashboard (React) | 2d | T1, T2, showcase_react |
| T7 | Subscription Upgrade/Downgrade Flows | 1.5d | T2, T6 |
| T8 | Testing & E2E | 1d | All above |

**Total Effort:** ~10 days

**Real Estate Use Cases:**
- Sellers purchase premium listing placement
- Featured property promotions (homepage carousel)
- Agent subscription tiers (basic: 5 listings, premium: unlimited)
- Pay-per-listing model for independent sellers
- Recurring revenue for agency

**Success Criteria:**
- [x] Stripe subscription lifecycle working
- [x] Pricing page with tier selection
- [x] Payment method management in user dashboard
- [x] Webhook processing for payment events
- [x] Upgrade/downgrade flows tested

---

## Priority 1 (P1): Teams Module - v0.77.0

**Why P1 for Real Estate:**
- Multi-agent agencies/brokerages need team management
- Role-based access (Owner, Broker, Agent, Admin)
- Property assignments by agent/team
- Commission tracking and reporting

**Implementation Tasks:**

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| T1 | Team & Membership Models | 1.5d | None |
| T2 | Role Hierarchy (Owner/Admin/Member) | 1.5d | T1 |
| T3 | Permission Decorators & Checks | 1d | T2 |
| T4 | Multi-Tenancy Row-Level Security | 2d | T1 |
| T5 | Team Creation & Settings UI | 1.5d | T1, showcase_react |
| T6 | Member Invitation System | 1.5d | T1, T5 |
| T7 | Team Dashboard (React) | 1.5d | T5 |
| T8 | Testing & E2E | 1d | All above |

**Total Effort:** ~8 days

**Real Estate Use Cases:**
- Agency creates team with multiple agents
- Broker assigns properties to specific agents
- Agent-level permissions (view all vs. own listings only)
- Team-scoped CRM (agents see team's contacts/deals)
- Commission splits and reporting by team

**Success Criteria:**
- [x] Team creation with owner/admin roles
- [x] Invitation system for new agents
- [x] Row-level security (agents see only team data)
- [x] Permission-based UI elements
- [x] Team dashboard with member management

---

## Priority 2 (P2): HTMX Theme - v0.78.0+

**Why P2 (Deferred):**
- React is default and sufficient for real estate use case
- HTMX provides alternative for simpler progressive enhancement
- Not critical for initial real estate agency launch

**Defer until:** Post-v0.77.0 (after SaaS Feature Parity)

---

## Priority 2 (P2): Notifications Module - v0.79.0

**Why P2 (Deferred):**
- Email notifications enhance UX but not blocking
- Can use third-party solutions (SendGrid, Mailgun) in interim
- Focus on core functionality first

**Future Real Estate Use Cases:**
- New listing email alerts to buyers
- Inquiry notifications to sellers/agents
- Viewing appointment reminders
- Offer status updates

**Defer until:** Post-v0.77.0 (after core modules complete)

---

## Dependencies Graph

```
v0.74.0 (React Default Theme) ✅ COMPLETE
    │
    ├──► v0.75.0 (CRM Theme) 📋 P0 - CRITICAL
    │       │
    │       ├──► Real Estate: Contact mgmt, deal pipeline
    │       └──► Foundation for billing/teams integration
    │
    ├──► v0.76.0 (Billing Module) 📋 P1 - HIGH
    │       │
    │       ├──► Real Estate: Premium listings, agent subscriptions
    │       └──► Requires: Stripe setup, payment flows
    │
    ├──► v0.77.0 (Teams Module) 📋 P1 - HIGH
    │       │
    │       ├──► Real Estate: Agency/brokerage management
    │       └──► Requires: Multi-tenancy, role-based permissions
    │
    ├──► v0.78.0+ (HTMX Theme) 📋 P2 - DEFERRED
    │
    └──► v0.79.0 (Notifications) 📋 P2 - DEFERRED
```

---

## Real Estate Agency Roadmap Consistency

### Phase 1: MVP Real Estate Site (v0.75.0)
**Goal:** Launch functional real estate agency website with property browsing and contact management

**Modules:**
- ✅ Auth (v0.63.0) - User registration, profiles
- ✅ Listings (v0.67.0) - Property search, details, galleries
- ✅ CRM Backend (v0.73.0) - Contact/deal APIs
- 🚧 CRM Frontend (v0.75.0) - Contact mgmt UI, deal pipeline

**User Experience:**
1. Buyers browse properties (Listings module)
2. Buyers contact agent (CRM inquiry creation)
3. Agent tracks inquiries in pipeline (CRM dashboard)
4. Agent schedules viewings (CRM notes)
5. Deal progresses through stages (CRM kanban)

**Launch Ready:** v0.75.0 (8 weeks)

---

### Phase 2: Monetization & Scaling (v0.76.0 - v0.77.0)
**Goal:** Add revenue streams and multi-agent support

**Modules:**
- 🚧 Billing (v0.76.0) - Premium listings, subscriptions
- 🚧 Teams (v0.77.0) - Agency/brokerage management

**Enhanced User Experience:**
1. Sellers purchase premium listing placement
2. Featured properties appear on homepage
3. Agencies manage multiple agents (Teams)
4. Role-based access (brokers vs agents)
5. Commission tracking per agent

**Production Ready:** v0.77.0 (16 weeks total)

---

### Phase 3: Enhancements (Post-v0.77.0)
**Goal:** Improve user engagement and retention

**Modules:**
- 📋 Notifications (v0.79.0) - Email alerts
- 📋 HTMX Theme (v0.78.0+) - Alternative frontend

**Future Features:**
- Email alerts for new listings matching buyer criteria
- Appointment reminder notifications
- Agent performance analytics
- Mobile app (React Native potential)

---

## Success Criteria (Overall Sprint)

### Technical Criteria:
- [x] v0.75.0: CRM React frontend deployed and tested
- [ ] v0.76.0: Billing module with Stripe integration working
- [ ] v0.77.0: Teams module with multi-tenancy operational
- [ ] All modules: 90% mean + 80% per-file test coverage
- [ ] E2E tests pass for complete real estate workflow

### Business Criteria:
- [ ] Real estate agency can launch with v0.75.0
- [ ] Revenue streams enabled by v0.76.0
- [ ] Multi-agent support working by v0.77.0
- [ ] Documentation complete for each release
- [ ] Migration guides for upgrading modules

### Real Estate Use Case Validation:
- [ ] Buyer can search and contact about properties
- [ ] Agent can manage contacts and track deals
- [ ] Seller can purchase premium listing placement
- [ ] Agency can onboard multiple agents with roles
- [ ] All workflows tested end-to-end

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| CRM frontend complexity exceeds estimates | Medium | High | Break into smaller incremental releases; ship minimal viable Kanban first |
| Stripe integration issues (webhooks, testing) | Medium | High | Use dj-stripe (proven), extensive webhook testing, Stripe test mode |
| Multi-tenancy bugs (data isolation) | High | Critical | Comprehensive row-level security tests, audit queries, security review |
| Performance issues with large property datasets | Low | Medium | Database indexing, pagination, lazy loading, optimize queries early |
| Module update conflicts with user customizations | Medium | Medium | Clear upgrade docs, state tracking (v0.71.0), rollback procedures |

---

## Next Steps (Immediate Actions)

### For v0.75.0 (CRM Theme):
1. ✅ Read CRM backend implementation (v0.73.0)
2. ✅ Study showcase_react patterns (v0.74.0)
3. [ ] Design Kanban board component architecture
4. [ ] Create CRM page wireframes (Dashboard, Contacts, Deals)
5. [ ] Implement TanStack Query hooks for CRM APIs
6. [ ] Build shadcn/ui Kanban board component
7. [ ] Add drag-and-drop deal stage transitions

### For v0.76.0 (Billing):
1. [ ] Research dj-stripe best practices
2. [ ] Design subscription tier structure (Free, Basic, Premium)
3. [ ] Plan Stripe webhook handling architecture
4. [ ] Define billing dashboard UX (payment methods, invoices)

### For v0.77.0 (Teams):
1. [ ] Design multi-tenancy data model
2. [ ] Plan role hierarchy (Owner → Broker → Agent)
3. [ ] Define permission matrix (who can do what)
4. [ ] Research Django row-level security patterns

---

## Notes

### Real Estate-Specific Considerations:
- **Listings Module** already generic enough for properties
- **CRM Module** perfect for buyer/seller/agent contacts
- **Billing Module** enables premium listing revenue model
- **Teams Module** supports multi-agent brokerages
- React frontend (v0.74.0) provides modern UX for property browsing

### Why This Order Makes Sense:
1. **v0.75.0 (CRM Theme)** - Unlocks contact management UX (critical for agencies)
2. **v0.76.0 (Billing)** - Adds revenue streams (premium listings)
3. **v0.77.0 (Teams)** - Scales to multi-agent operations
4. **v0.78.0+ (HTMX/Notifications)** - Nice-to-haves, defer post-launch

### Alternative Approaches Considered:
- ❌ **Do Billing before CRM Theme**: Rejected - CRM UX more critical than monetization for MVP
- ❌ **Build custom real estate module**: Rejected - Listings + CRM already cover core needs
- ❌ **Skip Teams module**: Rejected - Multi-agent support is competitive differentiator

---

## Authoritative References

- **Roadmap:** [roadmap.md](../technical/roadmap.md)
- **Decisions:** [decisions.md](../technical/decisions.md)
- **Architecture:** [decisions.md §Module & Theme Architecture](../technical/decisions.md#module-theme-architecture)
- **Plan/Apply System:** [decisions.md §Plan/Apply Architecture](../technical/decisions.md#planapply-architecture)

---

**Sprint Plan Created:** 2026-02-06
**Target Releases:** v0.75.0 (CRM Theme), v0.76.0 (Billing), v0.77.0 (Teams)
**Primary Goal:** Enable production-ready Real Estate Agency website with QuickScale + React
