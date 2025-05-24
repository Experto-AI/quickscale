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

## Technical Implementation

### Database Models
- **CreditAccount**: User's credit balance and account info
- **CreditTransaction**: Ledger of all credit movements
- **StripeProduct**: Local cache of Stripe products (subscriptions and pay-as-you-go)
- **StripeCustomer**: User linkage to Stripe customer records
- **UserSubscription**: User's subscription status and billing
- **Service**: Service definitions and credit costs

### Stripe Integration Models
- **StripeProduct**: Mirrors Stripe Products with local caching
  - Stores product information (name, description, pricing)
  - Contains metadata for credit amounts and billing intervals
  - Syncs bidirectionally with Stripe API
  - Supports both subscription (`interval='month'`) and one-time (`interval='one-time'`) products
- **StripeCustomer**: Links Django users to Stripe customer records
  - Maintains customer ID mapping for payment processing
  - Stores customer metadata and billing preferences

### Credit Operations
- **Atomic Transactions**: All credit operations use database transactions
- **Balance Calculation**: Real-time balance calculation from transaction history
- **Expiration Handling**: Automated expiration of subscription credits
- **Priority Logic**: Implemented in credit consumption methods
- **Stripe Sync**: Automatic synchronization with Stripe products and prices

### Integration Points
- **Stripe Products API**: Primary source for all product and pricing data
- **Stripe Checkout**: Unified checkout experience for all purchase types
- **Webhook Handling**: Real-time processing of payment and subscription events
- **Product Synchronization**: Bidirectional sync between local and Stripe data
- **Email Notifications**: Automated notifications for billing events
- **API Endpoints**: RESTful API for credit operations

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