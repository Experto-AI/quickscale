# QuickScale Credit System

## Overview

The QuickScale credit system is a flexible billing and usage tracking system that supports multiple payment models and credit types. Users can purchase credits through different methods, and these credits are consumed when using various services and products within the platform.

**Important**: Stripe Products serve as the **source of truth** for all pricing and plan information. The system syncs from Stripe to maintain consistency and uses Stripe Products for both subscription plans and pay-as-you-go credit purchases.

## Credit Types

### 1. Pay-as-You-Go Credits
- **Purchase**: One-time payment via Stripe Products (interval = 'one-time')
- **Expiration**: Never expire
- **Consumption Priority**: Consumed **after** subscription credits are exhausted
- **Use Case**: Perfect for occasional users or as backup credits for subscription users
- **Implementation**: Stripe Products with `interval='one-time'` and credit amounts in metadata

### 2. Subscription Credits
- **Purchase**: Monthly subscription via Stripe Products (interval = 'month')
- **Expiration**: Expire at the end of each billing period
- **Consumption Priority**: Consumed **first** before pay-as-you-go credits
- **Renewal**: Automatically allocated each billing cycle
- **Rollover**: Unused credits do NOT roll over to the next period
- **Implementation**: Stripe Products with `interval='month'` and monthly credit allocations

## Subscription Plans

### Basic Plan
- **Billing**: Monthly subscription (Stripe Product with interval='month')
- **Credits**: Standard monthly credit allocation (defined in Stripe Product metadata)
- **Price**: Standard per-credit rate
- **Target**: Regular users with predictable usage

### Pro Plan
- **Billing**: Monthly subscription (Stripe Product with interval='month')  
- **Credits**: Higher monthly credit allocation (defined in Stripe Product metadata)
- **Price**: Lower per-credit rate (bulk discount)
- **Target**: Power users with high usage requirements

## Stripe Integration Architecture

### Stripe as Source of Truth
- **All pricing information** is maintained in Stripe Products
- **Credit amounts** are stored in Stripe Product metadata
- **Local StripeProduct model** syncs from Stripe API to cache data locally
- **User interface** displays information from local StripeProduct models
- **Purchases** are processed through Stripe Checkout using Stripe Product/Price IDs

### Product Configuration
- **Subscription Plans**: Stripe Products with `interval='month'` 
- **Pay-as-You-Go**: Stripe Products with `interval='one-time'`
- **Credit Metadata**: Credit amounts stored in Stripe Product metadata
- **Pricing**: Handled entirely through Stripe Price objects

### Synchronization
- **Admin Interface**: Provides "Sync from Stripe" functionality
- **Automatic Sync**: Webhook handling keeps local data current
- **Manual Sync**: Admin actions for bulk synchronization
- **Error Handling**: Graceful fallback when Stripe is unavailable

## Credit Consumption Logic

### Priority System
The system follows a strict consumption priority to maximize value for users:

1. **First**: Current period subscription credits (if any active subscription)
2. **Second**: Pay-as-you-go credits (oldest first, FIFO)

### Example Scenarios

**Scenario 1: Subscription User with Backup Credits**
- User has Basic plan: 1,000 subscription credits (expires monthly)
- User purchased: 500 pay-as-you-go credits (never expire)
- Service usage: 1,200 credits needed
- **Consumption**: 1,000 from subscription + 200 from pay-as-you-go
- **Remaining**: 300 pay-as-you-go credits

**Scenario 2: Pay-as-You-Go Only User**
- User has: 800 pay-as-you-go credits
- Service usage: 300 credits needed
- **Consumption**: 300 from pay-as-you-go credits
- **Remaining**: 500 pay-as-you-go credits

**Scenario 3: Hybrid User After Subscription Expires**
- User's subscription expired with 0 remaining subscription credits
- User has: 400 pay-as-you-go credits remaining
- Service usage: 200 credits needed
- **Consumption**: 200 from pay-as-you-go credits
- **Remaining**: 200 pay-as-you-go credits

## Services & Products

### Credit Consumption
- Each service and product has a **configurable credit cost**
- Credit costs can vary based on:
  - Service complexity
  - Resource requirements
  - Processing time
  - External API costs

### Pre-Flight Validation
- Before any service usage, the system checks available credits
- If insufficient credits: Service usage is **blocked** with clear error message
- User is prompted to purchase more credits or upgrade subscription

### Usage Tracking
- All service usage is tracked in real-time
- Credit consumption is logged with:
  - Service/product used
  - Credits consumed
  - Credit source (subscription vs. pay-as-you-go)
  - Timestamp
  - User ID

## User Experience Features

### Credit Dashboard
Users can view:
- **Current Balance**: Total credits available
- **Balance Breakdown**: Subscription vs. pay-as-you-go credits
- **Expiration Timeline**: When subscription credits expire
- **Usage History**: Recent credit consumption
- **Low Balance Warnings**: Proactive notifications

### Payment History
Users have access to:
- **Subscription Payments**: All recurring billing transactions
- **Credit Purchases**: All one-time credit purchases
- **Receipts**: Downloadable receipts for all transactions
- **Refunds**: Tracking of any refunds or disputes

### Subscription Management
Users can:
- **View Plan**: Current subscription status and details
- **Upgrade/Downgrade**: Change plans with prorated pricing
- **Cancel**: Cancel subscription with clear terms
- **Billing History**: View all past invoices

## Admin & Support Features

### User Account Management
Admins can:
- **View Any User**: Access complete user credit status
- **Manual Adjustments**: Add/remove credits with reason tracking
- **Plan Changes**: Override subscription plans for support cases
- **Payment Issues**: Resolve billing and payment problems

### Analytics Dashboards
- **Revenue Analytics**: MRR, revenue by plan type, growth trends
- **User Analytics**: Active users, churn rates, usage patterns
- **Cashflow**: Real-time revenue, renewals, failed payments
- **Service Performance**: Popular services, profitability analysis

### Audit & Compliance
- **Complete Audit Log**: All admin actions tracked
- **Security Controls**: Role-based access for sensitive operations
- **User Notifications**: Users notified of account changes
- **Compliance Reporting**: Financial transaction reporting

### Enhanced Payment History
Users have access to comprehensive payment tracking:
- **Receipt Generation**: Automatic receipt creation with unique receipt numbers (`RCP-YYYYMMDD-XXXXXX` format)
- **Payment Lifecycle**: Complete tracking from payment intent to completion with status updates
- **Multiple Payment Types**: Credit purchases, subscription payments, plan changes, and refunds
- **Downloadable Receipts**: JSON-based receipt data with all transaction details
- **Stripe Integration**: Direct links to Stripe payment intents, subscriptions, and invoices
- **Audit Compliance**: Complete payment history for tax and compliance requirements

### Enhanced Subscription Management
Users can:
- **View Plan**: Current subscription status with detailed billing period information
- **Plan Comparison**: Side-by-side comparison of Basic vs Pro plans with cost per credit calculations
- **Upgrade/Downgrade**: Seamless plan changes through Stripe Checkout with automatic credit transfer
- **Credit Transfer Visibility**: Clear display of how remaining subscription credits transfer to pay-as-you-go
- **Billing History**: Complete payment history with downloadable receipts
- **Subscription Status**: Real-time subscription status with days until renewal
- **Cancel**: Cancel subscription with clear terms and credit preservation
## Plan Change Management

### Overview
The system provides comprehensive plan upgrade and downgrade functionality with automatic credit transfer and prorated billing through Stripe Checkout sessions.

### Plan Change Flow
1. **User Initiation**: Users can upgrade or downgrade their subscription plans through the admin dashboard
2. **Checkout Session**: All plan changes use Stripe Checkout for user consent and secure payment processing
3. **Credit Transfer**: Remaining subscription credits automatically transfer to pay-as-you-go credits
4. **New Plan Activation**: New subscription plan becomes active with immediate credit allocation
5. **Payment Recording**: Complete payment records generated for audit compliance

### Credit Transfer Logic
- **Subscription Credit Removal**: Existing subscription credits are deducted using negative SUBSCRIPTION transactions
- **Pay-as-you-go Addition**: Same credits are added as PURCHASE type (pay-as-you-go, never expire)
- **Atomic Operations**: All transfers use database transactions to ensure data integrity
- **Audit Trail**: Complete logging of credit transfers with descriptive transaction records

### Implementation Details
- **Common Function**: `handle_plan_change_credit_transfer()` ensures consistency across view handlers and webhooks
- **Duplicate Prevention**: Built-in safeguards prevent double credit allocation or payment processing
- **Webhook Integration**: Real-time processing of Stripe subscription change events
- **User Experience**: Success pages display detailed summaries of credit transfers and charges

### Plan Change Types
- **Upgrades**: Higher-tier plans with more monthly credits and better per-credit rates
- **Downgrades**: Lower-tier plans with fewer monthly credits
- **Prorated Billing**: Stripe automatically handles prorated charges for plan changes
- **Immediate Effect**: Plan changes take effect immediately after successful payment

## Technical Implementation

### Database Models

#### Core Credit Models
- **CreditAccount**: User's credit balance and account info with advanced balance calculation methods
- **CreditTransaction**: Comprehensive ledger of all credit movements with expiration support
- **Service**: Service definitions and credit costs with usage tracking
- **ServiceUsage**: Tracks individual service consumption events linked to credit transactions

#### Subscription Management Models
- **UserSubscription**: Complete subscription lifecycle management
  - **Status Management**: 8 subscription states (active, canceled, past_due, unpaid, incomplete, incomplete_expired, trialing, paused)
  - **Billing Period Tracking**: `current_period_start`, `current_period_end` for precise billing cycles
  - **Stripe Integration**: Links to Stripe subscription IDs and product IDs
  - **Cancellation Management**: `cancel_at_period_end`, `canceled_at` for graceful subscription ending
  - **Credit Allocation**: `allocate_monthly_credits()` method for automatic credit provisioning

#### Payment Processing Models
- **Payment**: Comprehensive payment transaction tracking
  - **Multiple Payment Types**: CREDIT_PURCHASE, SUBSCRIPTION, REFUND support
  - **Stripe Integration**: Links to payment intents, subscriptions, and invoices
  - **Receipt Generation**: Automatic receipt creation with `generate_receipt_data()` method
  - **Audit Trail**: Complete payment lifecycle tracking with receipt data in JSON format
  - **Invoice Support**: `stripe_invoice_id` field for immediate charges (added in Sprint 9)

### Enhanced Stripe Integration Models
- **StripeProduct**: Advanced Stripe product management with local caching
  - **Product Information**: Name, description, pricing with currency support
  - **Credit Configuration**: `credit_amount` field for credit allocation amounts
  - **Display Control**: `display_order` for frontend presentation ordering
  - **Billing Intervals**: Supports monthly, yearly, and one-time billing cycles
  - **Utility Methods**:
    - `price_per_credit` property for cost calculations
    - `is_subscription` and `is_one_time` properties for type identification
    - `sync_with_stripe()` method for bidirectional synchronization
  - **Stripe Integration**: `stripe_id` and `stripe_price_id` for API mapping

- **StripeCustomer**: Enhanced Django-Stripe customer linking
  - **Customer Mapping**: One-to-one relationship with Django users
  - **Stripe Integration**: `stripe_id` for customer identification
  - **Contact Information**: Email and name synchronization with Stripe
  - **Audit Trail**: Creation and modification timestamps

### Enhanced Credit Operations
- **Atomic Transactions**: All credit operations use database transactions for data integrity
- **Advanced Balance Calculation**: Multiple balance calculation methods for different use cases:
  - `get_balance()`: Simple total balance calculation
  - `get_balance_by_type()`: Balance breakdown by credit type
  - `get_balance_by_type_available()`: Priority-based balance with expiration filtering
  - `get_available_balance()`: Real-time balance excluding expired subscription credits
- **Priority Consumption Logic**:
  - `consume_credits_with_priority()`: Enforces subscription-first, then pay-as-you-go consumption
  - Automatic expiration validation during consumption
  - FIFO (First-In-First-Out) consumption within credit types
- **Expiration Handling**:
  - Automated expiration of subscription credits based on billing periods
  - Real-time filtering of expired credits from balance calculations
  - Graceful handling of expired credits without data loss
- **Stripe Sync**: Bidirectional synchronization with Stripe products and prices
- **Audit Trail**: Complete transaction logging with credit source tracking

### Integration Points
- **Stripe Products API**: Primary source for all product and pricing data
- **Stripe Checkout**: Unified checkout experience for all purchase types including plan changes
- **Webhook Handling**: Real-time processing of payment, subscription, and plan change events
- **Product Synchronization**: Bidirectional sync between local and Stripe data with `sync_with_stripe()` methods
- **Email Notifications**: Automated notifications for billing events and plan changes
- **Enhanced API Endpoints**:
  - Credit management endpoints with priority consumption logic
  - Plan change management endpoints (`create_plan_change_checkout`, `plan_change_success`)
  - Subscription management with upgrade/downgrade support
  - Receipt generation and download endpoints
  - Real-time balance calculation endpoints with expiration filtering

## Security & Compliance

### Payment Security
- **PCI Compliance**: All payment data handled securely via Stripe
- **Fraud Detection**: Monitoring for unusual payment patterns
- **Encryption**: Sensitive credit data encrypted at rest

### Access Controls
- **User Isolation**: Users can only access their own credit data
- **Admin Controls**: Role-based access for admin operations
- **Audit Trails**: Complete logging of all financial operations

### Data Protection
- **GDPR Compliance**: User data handling follows GDPR requirements
- **Data Retention**: Clear policies for financial data retention
- **Right to Deletion**: Procedures for user data deletion requests 