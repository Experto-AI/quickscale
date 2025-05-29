# QuickScale Development Roadmap

## Components Already Implemented

1. **Authentication & User Management**:
   - ✅ User registration, login, session management
   - ✅ Basic user profiles
   - ✅ Admin/user role separation
   - ✅ Email-only authentication with django-allauth
   - ✅ HTMX integration for auth forms
   - ✅ Email verification system with mandatory verification
   - ✅ Transactional email templates

2. **Core Infrastructure**:
   - ✅ Database connections (PostgreSQL)
   - ✅ API routing framework (Django)
   - ✅ Project structure with proper separation of concerns
   - ✅ Docker containerization
   - ✅ Development tools and CLI commands
   - ✅ Basic security setup
   - ✅ HTMX integration for dynamic content loading
   - ✅ Alpine.js for client-side interactivity
   - ✅ CLI improvements and error handling

3. **UI Components**:
   - ✅ Public pages (home, about, contact)
   - ✅ User dashboard
   - ✅ Admin dashboard
   - ✅ User settings
   - ✅ Bulma CSS for styling

4. **Payment Foundation**:
   - ✅ Basic Stripe integration
   - ✅ Basic customer management (create, link to user)
   - ✅ Product listing and viewing
   - ✅ Basic product management in admin
   - ✅ Basic checkout flow
   - ✅ Payment confirmation
   - ✅ Stripe webhook handling (basic structure)
   - ✅ Checkout success/error pages
   - ✅ Payment history and receipts (Sprint 8)
   - ❌ Subscription management system
   - ❌ Advanced webhook event processing
   - ❌ Payment method management
   - ❌ Customer billing history

5. **Credit System Foundation**:
   - ✅ Basic credit account system (Sprint 1)
   - ✅ Manual credit management for admins (Sprint 2)
   - ✅ Basic service credit consumption (Sprint 3)
   - ✅ Pay-as-you-go credit purchase (Sprint 4)
   - ✅ Basic monthly subscription system (Sprint 6)
   - ✅ Credit type priority system (Sprint 7)
   - ✅ Payment history & receipts (Sprint 8)

For more details refer to the [CHANGELOG](CHANGELOG.md).

## System Architecture Overview

The QuickScale credit system supports multiple payment models and credit types with flexible billing options. For complete details about the credit system architecture, consumption logic, and technical implementation, see the [Credit System Documentation](docs/CREDIT_SYSTEM.md).

**Key Features:**
- **Two Credit Types**: Pay-as-you-go (never expire) and subscription credits (monthly expiration)
- **Three Purchase Options**: Basic plan, Pro plan, and one-time credit purchases
- **Smart Consumption**: Subscription credits consumed first, then pay-as-you-go credits
- **Variable Costs**: Each service/product consumes configurable credit amounts
- **Real-time Tracking**: Complete usage and payment history for users and admins

## Development Sprints

---

### Sprint 10: Admin Support Dashboard (v0.22.0)
**Goal**: Admin tools to help users with credit/subscription issues

**Backend Implementation:**
- [ ] Create admin views to search and view any user's account
- [ ] Add admin tools for manual credit adjustments
- [ ] Create audit logging for all admin actions
- [ ] Add user account override capabilities
- [ ] Add admin tools to initiate full or partial Stripe refunds for user payments.
- [ ] Implement backend logic to search and retrieve failed Stripe transactions by user or transaction ID.
- [ ] Add functionality to reconcile transactions reported by users as charged but not registered in the system.
- [ ] Add backend logic to cancel a user's future subscription periods via the Stripe API.

**Frontend Implementation:**
- [ ] Create admin dashboard with user search
- [ ] Show complete user credit status (same view as user dashboard)
- [ ] Add admin tools for credit adjustments and subscription changes
- [ ] Display admin action history and audit logs
- [ ] Add UI elements in the admin dashboard to view user payment history with Stripe transaction details.
- [ ] Include an option for admins to initiate refunds directly from the payment history view, allowing specification of refund amount for partial refunds.
- [ ] Add a search feature for administrators to find specific transactions (including failed ones) by user or transaction ID.
- [ ] Implement a view or tool to manually register or investigate transactions that are reported as charged by the user but are missing in the system.
- [ ] Add a UI element in the admin dashboard to cancel a user's future subscription periods.

**Testing:**
- [ ] Tests for admin user account access, check them
- [ ] Tests for admin credit operations, check them
- [ ] Tests for audit logging, check them
- [ ] Tests for initiating refunds via the admin tools, including partial refunds.
- [ ] Tests for searching and retrieving failed transactions.
- [ ] Tests for the transaction reconciliation process.
- [ ] Tests for the functionality to cancel future subscription periods.

**Notes**:
- We don't need backward compatibility with previous versions of the codebase.
- We don't need django migrations, we could replace previous tables.
- When testing remember to check the quickscale codebase not a genrated project
- In Stripe, the source of truth, we have 3 plans to sync: Basic, Pro, and one-time credit purchases.

**Validation**: Admin can search any user, view their complete credit status, and make adjustments

---

### Sprint 11: Basic Analytics Dashboard (v0.23.0)
**Goal**: Simple revenue and user analytics for business insights

**Backend Implementation:**
- [ ] Create basic analytics calculations (total revenue, active subscriptions)
- [ ] Add user count metrics (total, active subscribers, credit purchasers)
- [ ] Calculate most popular services by credit consumption
- [ ] Add monthly revenue tracking

**Frontend Implementation:**
- [ ] Create `/admin/analytics/` page with key metrics
- [ ] Show total revenue, subscription revenue, credit purchase revenue
- [ ] Display user counts and subscription plan distribution
- [ ] Add simple charts for monthly revenue trends

**Testing:**
- [ ] Tests for analytics calculations, check them
- [ ] Tests for analytics dashboard display, check them
- [ ] Integration tests for real-time metrics, check them

**Notes**:
- We don't need backward compatibility with previous versions of the codebase.
- We don't need django migrations, we could replace previous tables.
- When testing remember to check the quickscale codebase not a genrated project
- In Stripe, the source of truth, we have 3 plans to sync: Basic, Pro, and one-time credit purchases.

**Validation**: Admin can view business metrics and revenue analyticds

---

### Sprint 12: Refactor and Maintenance (v0.24.0)
**Goal**: Refactor and maintain codebase

**Backend Implementation:**
- [ ] Iterate code-tree and remove all unused functions and classes
- [ ] Iterate code-tree and check each file for CONTRIBUTING rules
