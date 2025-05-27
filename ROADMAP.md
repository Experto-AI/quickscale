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
   - ❌ Subscription management system
   - ❌ Advanced webhook event processing
   - ❌ Payment method management
   - ❌ Customer billing history

5. **Credit System Foundation**:
   - ✅ Basic credit account system (Sprint 1)
   - ✅ Manual credit management for admins (Sprint 2)
   - ✅ Basic service credit consumption (Sprint 3)
   - ✅ Pay-as-you-go credit purchase (Sprint 4)

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

### Sprint 4: Pay-as-You-Go Credit Purchase (v0.16.0) ✅ COMPLETED
**Goal**: Users can buy credits that never expire

**Backend Implementation:**
- [X] Add `credit_type` field to `CreditTransaction` (PURCHASE, CONSUMPTION, ADMIN)
- [X] Create credit purchase packages (100, 500, 1000 credits)
- [X] Integrate Stripe Checkout for one-time payments
- [X] Add webhook handling for successful payments
- [X] Automatic credit allocation on payment success

**Frontend Implementation:**
- [X] Create `/dashboard/buy-credits/` page with package options
- [X] Add Stripe Checkout integration with package selection
- [X] Create payment success/failure pages
- [X] Show purchase history in credit transactions

**Testing:**
- [X] Tests for credit purchase flow
- [X] Tests for Stripe webhook processing
- [X] Integration tests for complete purchase process

**Validation**: User can purchase credits with real money and immediately see updated balance ✅

**FIXED**:
- [X] Refactor, use Synced STRIPE INTERGRATION -> STRIPE PRODUCTS instead of CREDITS -> CREDIT PURCHASES PACKAGES
- [X] Clarify CREDIT SYSTEM docs for that

---

### Sprint 5: Refactor and Maintenance (v0.17.0)
**Goal**: Improve code quality, user flow and maintainability

**Django Admin:**
- [X] Update Technical DOCs, each diagram should be updated to reflect the new structure
- [X] Fix credits synced from Stripe for each plan (are all 1000?)
   - [X] Code created in sync_product_from_stripe, sync metadata credit_amount.
   - [X] Also sync metadata display_order.
   - [X] Fail gracefully by default, do not create defaults.
   - [X] Human test
- [X] Remove Django Admin ADD STRIPE PRODUCT button in STRIPE INTEGRATION -> STRIPE PRODUCTS
   - [X] Human test
- [X] Analyze if Django Admin ACCOUNTS -> Email Address could be grouped with USERS -> Customs Users
   - [X] Human test
- [X] Analyze if also Django Admin STRIPE INTEGRATION -> STRIPE USERS could be grouped.
      Not DONE, is not convenient.

**Backend and Frontend Implementation:**
- [X] Admin: rename Dashboard to Admin Dashboard to differentiate user dashboard ("My Dashboard")
      In codebase, backend and frontend.
- [X] Group all migrations into one file

**Testing:**
- [X] Update all unit tests to reflect changes

**Validation**: Refactor completed, user flows improved, and codebase more maintainable

---

### Sprint 6: Basic Monthly Subscription (v0.18.0) ✅ COMPLETED
**Goal**: Implement Basic subscription plan with monthly credits

**Backend Implementation:**
- [X] Create `UserSubscription` model with status and billing date
- [X] Add `credit_type` field: SUBSCRIPTION vs PAY_AS_YOU_GO
- [X] Create Stripe subscription product for Basic plan (**Note**: Create this product and its pricing in your Stripe account first, then sync to your local StripeProduct model.)
- [X] Add subscription webhook handling

**Frontend Implementation:**
- [X] Create `/admin_dashboard/subscription/` page showing current plan
- [X] Add "Subscribe to Basic" button with Stripe Checkout
- [X] Show subscription status and next billing date
- [X] Display credit breakdown (subscription vs pay-as-you-go)

**Testing:**
- [X] Tests for subscription creation, check them
- [X] Tests for subscription credit allocation, check them
- [X] Integration tests for subscription flow, check them

**Validation**: User can subscribe to Basic plan and receive monthly credits automatically ✅

---

### Sprint 7: Credit Type Priority System (v0.19.0)
**Goal**: Implement subscription credits consumed first, then pay-as-you-go

**Backend Implementation:**
- [ ] Add credit expiration logic for subscription credits
- [ ] Implement priority consumption (subscription credits first)
- [ ] Update `consume_credits()` method with priority logic
- [ ] Add credit expiration handling on billing cycle

**Frontend Implementation:**
- [ ] Update credit balance display to show breakdown by type
- [ ] Add expiration dates for subscription credits
- [ ] Show which credit type is being consumed during service usage

**Testing:**
- [ ] Tests for credit priority consumption, check them
- [ ] Tests for credit expiration logic, check them
- [ ] Integration tests for mixed credit scenarios, check them

**Notes**:
- We don't need backward compatibility for credit types.
- We don't need django migrations, we could replace previous tables.

**Validation**: User with both credit types sees subscription credits consumed first

---

### Sprint 8: Pro Subscription Plan (v0.20.0)
**Goal**: Add Pro plan with more credits at better rate

**Backend Implementation:**
- [ ] Add Pro plan as a Stripe subscription product (**Note**: Create this product and its pricing in your Stripe account first, then sync to your local StripeProduct model.)
- [ ] Add plan upgrade/downgrade logic
- [ ] Handle prorated billing for plan changes

**Frontend Implementation:**
- [ ] Add Pro plan option to subscription page
- [ ] Create plan comparison table (Basic vs Pro)
- [ ] Add upgrade/downgrade buttons for existing subscribers
- [ ] Show savings calculation for Pro plan

**Testing:**
- [ ] Tests for Pro plan subscription, check them
- [ ] Tests for plan upgrades/downgrades, check them
- [ ] Integration tests for multiple plan types, check them

**Validation**: User can choose between Basic and Pro plans and upgrade/downgrade

---

### Sprint 9: Payment History & Receipts (v0.21.0)
**Goal**: Complete payment tracking and receipt system

**Backend Implementation:**
- [ ] Create `Payment` model for all payment tracking
- [ ] Link payments to credit transactions and subscriptions
- [ ] Generate receipt data for all payment types
- [ ] Add payment status tracking (success, failed, refunded)

**Frontend Implementation:**
- [ ] Create `/admin_dashboard/payments/` page with payment history
- [ ] Show detailed payment information (amount, date, type, status)
- [ ] Add downloadable receipts for each payment
- [ ] Separate views for subscription payments vs credit purchases

**Testing:**
- [ ] Tests for payment tracking, check them
- [ ] Tests for receipt generation, check them
- [ ] Integration tests for payment history display, check them

**Validation**: User can view complete payment history with downloadable receipts

---

### Sprint 10: Admin Support Dashboard (v0.22.0)
**Goal**: Admin tools to help users with credit/subscription issues

**Backend Implementation:**
- [ ] Create admin views to search and view any user's account
- [ ] Add admin tools for manual credit adjustments
- [ ] Create audit logging for all admin actions
- [ ] Add user account override capabilities

**Frontend Implementation:**
- [ ] Create admin dashboard with user search
- [ ] Show complete user credit status (same view as user dashboard)
- [ ] Add admin tools for credit adjustments and subscription changes
- [ ] Display admin action history and audit logs

**Testing:**
- [ ] Tests for admin user account access, check them
- [ ] Tests for admin credit operations, check them
- [ ] Tests for audit logging, check them

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

**Validation**: Admin can view business metrics and revenue analyticds

---

### Sprint 12: Refactor and Maintenance (v0.24.0)
**Goal**: Refactor and maintain codebase

**Backend Implementation:**
- [ ] Iterate code-tree and remove all unused functions and classes
- [ ] Iterate code-tree and check each file for CONTRIBUTING rules
