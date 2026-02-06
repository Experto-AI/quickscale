# Sprint Plan: Real Estate Agency Focus (v0.75.0 - v0.79.0)

## Sprint Goal
Prioritize and complete modules essential for building a production-ready Real Estate Agency website using QuickScale with React frontend, following the agency's phased launch strategy.

## Context
User needs to create a Real Estate Agency web page using QuickScale. The sprint plan aligns QuickScale releases with the agency's 4-phase launch strategy: static site → social links → property listings → social media integration.

## Duration
Estimated: 12-18 weeks (based on module complexity and dependencies)

## Current State (v0.74.0)

**✅ Completed:**
- React Default Theme (showcase_react) with shadcn/ui
- Auth Module (v0.63.0) - django-allauth integration
- Listings Module (v0.67.0) - generic base for vertical themes (backend only)
- CRM Module (v0.73.0) - API-only backend
- Plan/Apply System (v0.68.0-v0.71.0) - Terraform-style configuration

**📋 Next Release:** v0.75.0 - Listings Theme (React frontend for property listings)

## Real Estate Agency Phased Launch Strategy

The agency's website evolves through 4 business phases, each adding functionality:

| Phase | Business Goal | QuickScale Support | Timeline |
|-------|--------------|-------------------|----------|
| **Phase 1** | Static information site (about, services, contact) | ✅ v0.74.0 React Default Theme | **Now** |
| **Phase 2** | Link tree with social networks | 📋 v0.76.0 Social & Link Tree Module | ~6 weeks |
| **Phase 3** | Property listings (sell & rent) | 📋 v0.75.0 Listings Theme (React) | ~4 weeks |
| **Phase 4** | Social media integration (repost IG/TikTok/YouTube) | 📋 v0.76.0 Social & Link Tree Module | ~6 weeks |

> **Note**: v0.75.0 (Listings Theme) is developed before v0.76.0 (Social Module) because it requires more engineering effort. The agency can launch Phase 1 immediately and Phase 2 (link tree) can be built as a custom page while waiting for the Social module. Phases 2 & 4 are served by the same module (v0.76.0).

---

## Selected Tasks (Prioritized for Real Estate)

| Priority | Release | Module | Effort | Status | Agency Phase |
|----------|---------|--------|--------|--------|--------------|
| **P0** | v0.75.0 | Listings Theme (React) | 8d | 📋 Planned | **Phase 3** - Property sell/rent browsing |
| **P1** | v0.76.0 | Social & Link Tree Module | 7d | 📋 Planned | **Phase 2 & 4** - Social links + media embeds |
| **P2** | v0.77.0 | CRM Theme (React) | 7d | 📋 Planned | **Future** - Contact mgmt, deal pipeline |
| **P3** | v0.78.0 | Billing Module | 10d | 📋 Deferred | **Future** - Premium listings, subscriptions |
| **P3** | v0.79.0 | Teams Module | 8d | 📋 Deferred | **Future** - Multi-agent agency support |

---

## Agency Phase 1: Static Information Site (NOW)

**Status**: ✅ Ready — No new QuickScale release needed

**What the agency gets with v0.74.0:**
- React + shadcn/ui modern frontend
- Responsive layout with sidebar navigation
- Pre-built page templates (Dashboard, About, Contact)
- Professional design with Tailwind CSS
- SEO-friendly SPA with catch-all routing

**Agency Pages to Build (custom work on existing theme):**
- Home page with agency branding and hero section
- About page (team, mission, history)
- Services page (buying, selling, renting, property management)
- Contact page with form and location map
- Footer with basic social media icon links

**No QuickScale release required** — the agency can launch Phase 1 immediately.

---

## Priority 0 (P0): Listings Theme - v0.75.0

**Why P0 for Real Estate:**
- Property listings are the CORE business of a real estate agency
- Listings backend already exists (v0.67.0), needs React frontend only
- Enables property browsing with sell/rent filtering
- Highest engineering effort — start first for earliest delivery

**Implementation Tasks:**

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| T1 | Listings page layouts (grid, list, map views) | 1.5d | showcase_react (v0.74.0) |
| T2 | Property card component (image, price, type, location) | 1d | T1, shadcn/ui Card |
| T3 | Search and filter bar (price, type, location, bedrooms) | 1.5d | T1, React Hook Form |
| T4 | Property detail view with image gallery | 1.5d | T2, shadcn/ui Dialog |
| T5 | Sell vs Rent listing type filters and badges | 0.5d | T3 |
| T6 | Listings dashboard with stats and featured properties | 1d | T1, TanStack Query |
| T7 | SEO-friendly property pages (meta tags, structured data) | 0.5d | T4 |
| T8 | Integration Testing & E2E | 0.5d | All above |

**Total Effort:** ~8 days

**Real Estate Use Cases:**
- Buyers browse properties by type (sell/rent), price, location
- Property detail pages with image galleries and descriptions
- Featured properties on dashboard/homepage
- Search and filter for specific property criteria
- Responsive property cards for mobile browsing

**Success Criteria:**
- [ ] Property grid/list views with responsive cards
- [ ] Search and filter by price, type (sell/rent), location, bedrooms
- [ ] Property detail view with image gallery
- [ ] Live API integration with Listings backend (v0.67.0)
- [ ] Mobile-responsive design (shadcn/ui)
- [ ] SEO meta tags on property pages

---

## Priority 1 (P1): Social & Link Tree Module - v0.76.0

**Why P1 for Real Estate:**
- Agencies need social media presence (Instagram, TikTok, YouTube, Facebook)
- Link tree page is a quick win for agency branding
- Social media embeds showcase property videos and photos from social platforms
- Serves both Phase 2 (link tree) and Phase 4 (social media embeds)

**Implementation Tasks:**

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| T1 | SocialLink model (platform, url, icon, order, is_active) | 0.5d | None |
| T2 | Django Admin for social link management | 0.5d | T1 |
| T3 | REST API endpoints for social links | 0.5d | T1 |
| T4 | Link tree React page component | 1d | T3, showcase_react |
| T5 | Platform icon set (IG, TikTok, YouTube, FB, X, LinkedIn) | 0.5d | T4 |
| T6 | oEmbed resolver service for social media embeds | 1d | None |
| T7 | Instagram/TikTok/YouTube embed components | 1.5d | T6, React |
| T8 | Social feed gallery page (aggregate embeds) | 1d | T7 |
| T9 | Caching layer for embed data | 0.5d | T6 |
| T10 | Testing & E2E | 0.5d | All above |

**Total Effort:** ~7 days

**Real Estate Use Cases:**
- Agency link tree page with all social media profiles
- Embed Instagram posts showing property photos
- Embed TikTok/YouTube property tour videos
- Social feed page aggregating latest agency content
- Click tracking on social links (optional analytics)

**Success Criteria:**
- [ ] Configurable link tree page with social platform icons
- [ ] Admin interface for managing social links (add/remove/reorder)
- [ ] Instagram post/reel embed working
- [ ] TikTok video embed working
- [ ] YouTube video embed working
- [ ] Social feed gallery page with mixed platform embeds
- [ ] Embed caching to reduce API calls

---

## Priority 2 (P2): CRM Theme - v0.77.0

**Why P2 for Real Estate (deferred from original P0):**
- Contact management is valuable but not needed for initial website launch
- Agency can use external CRM tools initially
- CRM backend is complete (v0.73.0), frontend can wait
- Focus on public-facing features first (listings, social)

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
- [ ] Kanban board shows deals by stage (drag-and-drop)
- [ ] Contact list with search/filter by buyer/seller/agent
- [ ] Deal detail view with property association
- [ ] Live API integration with CRM backend (v0.73.0)
- [ ] Mobile-responsive design (shadcn/ui)

---

## Priority 3 (P3): Billing Module - v0.78.0

**Why P3 (Deferred):**
- Monetization is important but not needed for initial launch
- Agency should validate product-market fit with free listings first
- Can integrate Stripe later when revenue model is proven

**Defer until:** Post-v0.77.0 (after public-facing features and CRM)

**Future Real Estate Use Cases:**
- Premium/featured listing placement for sellers
- Agent subscription tiers (free, basic, premium)
- Pay-per-listing model for independent sellers
- Recurring revenue for agency

---

## Priority 3 (P3): Teams Module - v0.79.0

**Why P3 (Deferred):**
- Multi-agent support not needed until agency scales
- Single-agent operation sufficient for launch
- Focus on public-facing features first

**Defer until:** Post-v0.78.0 (after billing)

**Future Real Estate Use Cases:**
- Multi-agent agencies/brokerages
- Role-based access (Owner, Broker, Agent)
- Property assignments by agent
- Commission tracking

---

## Dependencies Graph

```
v0.74.0 (React Default Theme) ✅ COMPLETE
    │
    ├──► Agency Phase 1: Static Site (custom pages) ✅ READY NOW
    │
    ├──► v0.75.0 (Listings Theme) 📋 P0 - CRITICAL
    │       │
    │       ├──► Agency Phase 3: Property sell/rent browsing
    │       └──► Foundation for property-focused features
    │
    ├──► v0.76.0 (Social & Link Tree Module) 📋 P1 - HIGH
    │       │
    │       ├──► Agency Phase 2: Link tree with social links
    │       ├──► Agency Phase 4: Social media embeds (IG/TikTok/YouTube)
    │       └──► Requires: oEmbed protocol, embed components
    │
    ├──► v0.77.0 (CRM Theme) 📋 P2 - MEDIUM
    │       │
    │       └──► Future: Contact mgmt, deal pipeline
    │
    ├──► v0.78.0 (Billing Module) 📋 P3 - DEFERRED
    │
    └──► v0.79.0 (Teams Module) 📋 P3 - DEFERRED
```

---

## Real Estate Agency Phased Roadmap

### Phase 1: Static Agency Site (NOW - v0.74.0)
**Goal:** Launch professional agency website with static information

**Modules Used:**
- ✅ Auth (v0.63.0) - Admin access for content editing
- ✅ React Theme (v0.74.0) - Modern responsive frontend

**User Experience:**
1. Visitors see professional agency homepage
2. Browse About, Services, and Contact pages
3. Find agency location and contact details
4. See basic social media links in footer

**Launch Ready:** Immediately with v0.74.0

---

### Phase 2: Social Presence (v0.76.0)
**Goal:** Add link tree page and social network visibility

**Modules Used:**
- 🚧 Social & Link Tree (v0.76.0) - Social links page

**User Experience:**
1. Visitors access link tree page with all social profiles
2. One-click links to Instagram, TikTok, YouTube, Facebook
3. Professional branded link tree with platform icons
4. Agency shares link tree URL across marketing materials

**Enhanced with Phase 4:** Social media embeds added later

---

### Phase 3: Property Listings (v0.75.0)
**Goal:** Enable property browsing with sell/rent listings

**Modules Used:**
- ✅ Listings backend (v0.67.0) - Property data and API
- 🚧 Listings Theme (v0.75.0) - React property browsing UI

**User Experience:**
1. Buyers browse properties with grid/list views
2. Filter by type (sell/rent), price, location, bedrooms
3. View property details with image galleries
4. Contact agency about specific properties
5. Featured properties highlighted on dashboard

**Launch Ready:** v0.75.0 (4-6 weeks)

---

### Phase 4: Social Media Integration (v0.76.0)
**Goal:** Embed social media content (repost from Instagram/TikTok/YouTube)

**Modules Used:**
- 🚧 Social & Link Tree (v0.76.0) - Social media embeds

**User Experience:**
1. Agency reposts property tours from Instagram/TikTok
2. YouTube property walkthrough videos embedded on site
3. Social feed gallery shows latest agency content
4. Visitors engage with social content without leaving site

**Launch Ready:** v0.76.0 (6-8 weeks)

---

### Future Phases (Post-Launch)
**Goal:** Add internal management tools and monetization

**Modules:**
- 📋 CRM Theme (v0.77.0) - Internal contact/deal management
- 📋 Billing (v0.78.0) - Premium listings, agent subscriptions
- 📋 Teams (v0.79.0) - Multi-agent agency management

---

## Success Criteria (Overall Sprint)

### Technical Criteria:
- [ ] v0.75.0: Listings React frontend deployed and tested
- [ ] v0.76.0: Social & Link Tree module with embed support working
- [ ] v0.77.0: CRM React frontend deployed and tested
- [ ] All modules: 90% mean + 80% per-file test coverage
- [ ] E2E tests pass for complete real estate workflow

### Business Criteria (Agency Phases):
- [x] Phase 1: Agency can launch static site immediately (v0.74.0)
- [ ] Phase 2: Link tree page with social network links live
- [ ] Phase 3: Property listings browsable with sell/rent filters
- [ ] Phase 4: Social media content embedded on agency site
- [ ] Documentation complete for each release
- [ ] Migration guides for upgrading modules

### Real Estate Use Case Validation:
- [ ] Visitor can browse property listings and filter by sell/rent
- [ ] Visitor can view property details with image galleries
- [ ] Visitor can access social media link tree
- [ ] Agency can embed Instagram/TikTok/YouTube content
- [ ] All workflows tested end-to-end

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Listings frontend complexity exceeds estimates | Medium | High | Break into smaller incremental releases; ship property grid first |
| oEmbed API rate limits (Instagram/TikTok) | High | Medium | Implement caching layer, fallback to static links |
| Social platform API changes/deprecations | Medium | Medium | Use oEmbed standard (resilient), abstract platform-specific code |
| Performance issues with large image galleries | Low | Medium | Lazy loading, image optimization, CDN-ready static files |
| Module update conflicts with user customizations | Medium | Medium | Clear upgrade docs, state tracking (v0.71.0), rollback procedures |

---

## Next Steps (Immediate Actions)

### For Agency Phase 1 (Static Site — NOW):
1. ✅ Generate project with `quickscale plan myapp` (uses v0.74.0 React theme)
2. [ ] Customize homepage with agency branding
3. [ ] Create About, Services, Contact pages
4. [ ] Add agency location map and contact form
5. [ ] Deploy static site

### For v0.75.0 (Listings Theme):
1. ✅ Read Listings backend implementation (v0.67.0)
2. ✅ Study showcase_react patterns (v0.74.0)
3. [ ] Design property card component architecture
4. [ ] Create Listings page wireframes (Grid, Detail, Search)
5. [ ] Implement TanStack Query hooks for Listings APIs
6. [ ] Build shadcn/ui property card and filter components

### For v0.76.0 (Social & Link Tree):
1. [ ] Research oEmbed protocol and platform support
2. [ ] Design SocialLink data model
3. [ ] Plan embed component architecture (Instagram, TikTok, YouTube)
4. [ ] Define link tree page layout options

### For v0.77.0 (CRM Theme):
1. [ ] Design Kanban board component architecture
2. [ ] Create CRM page wireframes (Dashboard, Contacts, Deals)
3. [ ] Plan TanStack Query hooks for CRM APIs

---

## Notes

### Why Sprint Order Changed from Original Plan:
The original sprint plan (CRM → Billing → Teams) optimized for SaaS feature parity. The revised plan optimizes for the **agency's phased launch strategy**:

1. **Listings before CRM** — Public-facing property browsing is the agency's core business. CRM is internal tooling that can wait.
2. **Social before CRM** — Social media presence drives leads. Link tree and embeds have higher marketing ROI than internal CRM.
3. **CRM before Billing/Teams** — When internal tools are needed, contact management comes before monetization or multi-agent support.

### Real Estate-Specific Considerations:
- **Listings Module** already generic enough for properties (sell/rent types via categories)
- **Social Module** is new — serves both link tree (Phase 2) and embed (Phase 4) needs
- **CRM Module** deferred but still valuable for lead tracking later
- React frontend (v0.74.0) provides modern UX for all phases

### Alternative Approaches Considered:
- ❌ **Keep CRM as P0**: Rejected — agency's first need is public-facing, not internal tooling
- ❌ **Build custom social page without module**: Rejected — reusable module benefits all QuickScale projects
- ❌ **Separate link tree and embeds into two releases**: Rejected — they share social platform infrastructure
- ❌ **Skip Listings Theme (use CRM for property tracking)**: Rejected — listings UX is fundamentally different from CRM

---

## Authoritative References

- **Roadmap:** [roadmap.md](../technical/roadmap.md)
- **Decisions:** [decisions.md](../technical/decisions.md)
- **Architecture:** [decisions.md §Module & Theme Architecture](../technical/decisions.md#module-theme-architecture)
- **Plan/Apply System:** [decisions.md §Plan/Apply Architecture](../technical/decisions.md#planapply-architecture)

---

**Sprint Plan Created:** 2026-02-06
**Sprint Plan Updated:** 2026-02-06 (reordered for agency phased launch)
**Target Releases:** v0.75.0 (Listings Theme), v0.76.0 (Social & Link Tree), v0.77.0 (CRM Theme)
**Primary Goal:** Enable phased Real Estate Agency website: static → social links → listings → social embeds
