git statu# QuickScale Credit System

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

#### **Intelligent Expiration Handling**
When subscription credits are allocated, the system uses a sophisticated expiration logic:

1. **Primary Source**: Uses Stripe's `current_period_end` for precise billing cycle alignment
2. **Intelligent Fallback**: When Stripe billing data is unavailable, uses product interval information:
   - **Monthly subscriptions**: 31 days from allocation (ensures users get full month regardless of calendar)
   - **Annual subscriptions**: 365 days from allocation
   - **Unknown intervals**: Defaults to 31 days (user-favorable approach)

This approach ensures users always receive fair credit expiration periods, even when external billing data is temporarily unavailable.

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

### Advanced Balance Calculation
The system provides multiple balance calculation methods for different use cases:

- **Available Balance**: Real-time balance excluding expired subscription credits
- **Balance by Type**: Breakdown showing subscription vs. pay-as-you-go credits separately
- **Priority-Aware Balance**: Applies consumption priority logic to show accurate remaining credits
- **Expiration-Filtered Balance**: Automatically excludes expired credits from all calculations

### Consumption Process
When a service consumes credits, the system:

1. **Pre-flight Validation**: Checks available balance before allowing service usage
2. **Priority Application**: Consumes subscription credits first, then pay-as-you-go
3. **Expiration Awareness**: Automatically excludes expired subscription credits
4. **Transaction Safety**: Uses atomic operations to prevent race conditions
5. **Audit Trail**: Records complete consumption details for tracking and compliance

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

## Credit Expiration Management

### Automated Expiration Handling
The system provides comprehensive expiration management for subscription credits:

#### **Expiration Detection**
- **Real-time Filtering**: All balance calculations automatically exclude expired subscription credits
- **Cleanup Operations**: Periodic identification and processing of expired credits
- **Audit Preservation**: Expired credits remain in transaction history for compliance

#### **Expiration Warnings**
- **Early Warning System**: Identifies credits expiring within configurable timeframes (default: 7 days)
- **Detailed Breakdown**: Groups expiring credits by expiration date for precise tracking
- **User Notifications**: Enables proactive user communication about upcoming expirations

#### **Grace Period Logic**
- **User-Favorable Defaults**: Fallback expiration periods designed to benefit users
- **Calendar Independence**: Monthly subscriptions use 31-day fallback regardless of actual month length
- **Billing Alignment**: When available, uses exact Stripe billing period for precision

### Expiration Impact on Operations
- **Balance Calculations**: Expired credits automatically excluded from available balance
- **Priority Consumption**: Expiration status checked during credit consumption
- **Administrative Views**: Admins can track and manage expired credits across all users
- **Reporting**: Complete expiration analytics for business intelligence

## Services & Products

### AI Service Framework Integration
- **Service Template Generator**: `quickscale generate-service` creates AI services with automatic credit integration
- **BaseService Class**: All AI services inherit credit consumption logic automatically
- **Service Registration**: `@register_service` decorator automatically integrates services with credit system
- **Example Services**: Pre-built text processing, image processing, and data validation services

### Credit Consumption
- Each service and product has a **configurable credit cost**
- Credit costs can vary based on:
  - Service complexity
  - Resource requirements
  - Processing time
  - External API costs
- **Automatic Integration**: AI services generated with QuickScale framework automatically consume credits

### Pre-Flight Validation
- Before any service usage, the system checks available credits
- If insufficient credits: Service usage is **blocked** with clear error message
- User is prompted to purchase more credits or upgrade subscription
- **BaseService Integration**: Credit validation is automatic for all generated AI services

### Usage Tracking
- All service usage is tracked in real-time
- Credit consumption is logged with:
  - Service/product used
  - Credits consumed
  - Credit source (subscription vs. pay-as-you-go)
  - Timestamp
  - User ID
- **ServiceUsage Model**: Complete audit trail for all AI service consumption

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

### Service Management
Admins have comprehensive service administration capabilities:
- **Service Configuration**: Enable/disable services in real-time through admin dashboard
- **Usage Analytics**: Monitor service consumption patterns, credit usage, and user engagement
- **Performance Metrics**: Track total usage, unique users, and credits consumed per service
- **Bulk Operations**: Enable/disable multiple services simultaneously with audit logging
- **Real-time Monitoring**: Live service status updates via HTMX for immediate feedback
- **Detailed Analytics**: Service-specific analytics pages showing 30-day trends and usage patterns
- **Django Admin Integration**: Enhanced service management through Django admin with custom analytics views

### Analytics Dashboards
- **Revenue Analytics**: MRR, revenue by plan type, growth trends
- **User Analytics**: Active users, churn rates, usage patterns
- **Cashflow**: Real-time revenue, renewals, failed payments
- **Service Performance**: Popular services, profitability analysis

### Payment Support Tools
Admins have access to comprehensive payment support tools:
- **Payment Search**: Advanced search and filtering capabilities across all payment data
- **Payment Investigation**: Detailed payment analysis with user context and Stripe integration
- **Refund Processing**: Secure refund initiation with partial and full refund support
- **Audit Compliance**: Complete logging of all payment support activities

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
    - Unidirectional synchronization from Stripe to local database (Stripe as source of truth)
  - **Stripe Integration**: `stripe_id` and `stripe_price_id` for API mapping

- **StripeCustomer**: Enhanced Django-Stripe customer linking
  - **Customer Mapping**: One-to-one relationship with Django users
  - **Stripe Integration**: `stripe_id` for customer identification
  - **Contact Information**: Email and name synchronization with Stripe
  - **Audit Trail**: Creation and modification timestamps

### Enhanced Credit Operations
- **Atomic Transactions**: All credit operations use database transactions for data integrity
- **Performance Optimized**: Balance calculations use single database queries with conditional aggregation
- **Race Condition Prevention**: Concurrent access protection prevents double-spending scenarios
- **Input Validation**: Enhanced validation for amounts, descriptions, and business rules
- **Advanced Balance Calculation**: Multiple balance calculation methods for different use cases:
  - Simple total balance calculation
  - Balance breakdown by credit type (subscription vs. pay-as-you-go)
  - Priority-based balance with expiration filtering
  - Real-time balance excluding expired subscription credits
- **Priority Consumption Logic**:
  - Enforces subscription-first, then pay-as-you-go consumption
  - Automatic expiration validation during consumption
  - FIFO (First-In-First-Out) consumption within credit types
  - Pre-flight balance validation to prevent insufficient credit scenarios
- **Enhanced Expiration Handling**:
  - Automated expiration of subscription credits based on billing periods
  - Real-time filtering of expired credits from balance calculations
  - Graceful handling of expired credits without data loss
  - Early warning system for credits nearing expiration
  - Calendar-independent fallback logic for fair user treatment
- **Data Integrity Enforcement**:
  - Business rule validation at multiple levels (application and database)
  - Constraint enforcement for transaction types and amounts
  - Automatic data consistency checks
- **Stripe Sync**: Bidirectional synchronization with Stripe products and prices
- **Audit Trail**: Complete transaction logging with credit source tracking

### Integration Points
- **Stripe Products API**: Primary source for all product and pricing data
- **Stripe Checkout**: Unified checkout experience for all purchase types including plan changes
- **Webhook Handling**: Real-time processing of payment, subscription, and plan change events
- **Product Synchronization**: Bidirectional sync between local and Stripe data
- **Email Notifications**: Automated notifications for billing events and plan changes
- **API Architecture**:
  - Credit management with priority consumption logic
  - Plan change management with automatic credit transfer
  - Subscription management with upgrade/downgrade support
  - Receipt generation and download capabilities
  - Real-time balance calculation with expiration filtering
  - Pre-flight credit validation for service usage
  - Comprehensive audit trail for all credit operations

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

## Business Logic Patterns

### Priority Consumption Pattern
**Pattern**: Subscription credits consumed first, then pay-as-you-go credits
**Implementation**: 
- Balance calculations filter expired subscription credits automatically
- Consumption logic applies priority order during credit deduction
- FIFO (First-In-First-Out) within each credit type
- Pre-flight validation prevents insufficient credit scenarios

### Expiration Handling Pattern
**Pattern**: Automatic filtering of expired subscription credits from all calculations
**Implementation**:
- Real-time filtering in balance calculation methods
- Expiration date validation during consumption
- Grace period logic with user-favorable fallbacks
- Calendar-independent expiration periods (31 days for monthly)

### Atomic Transaction Safety Pattern
**Pattern**: All credit operations use database transactions with `select_for_update()`
**Implementation**:
- Race condition prevention through row-level locking
- Atomic credit addition and consumption operations
- Transaction rollback on validation failures
- Concurrent access protection prevents double-spending

### Balance Calculation Pattern
**Pattern**: Multiple calculation methods for different use cases
**Implementation**:
- `get_balance()`: Simple total balance
- `get_balance_by_type()`: Breakdown by credit type
- `get_available_balance()`: Excludes expired subscription credits
- `get_balance_by_type_available()`: Priority-aware with expiration filtering

### Service Integration Pattern
**Pattern**: Automatic credit consumption through BaseService class
**Implementation**:
- BaseService handles credit validation and consumption
- Service registration through decorators
- Pre-flight credit checking before service execution
- Automatic usage tracking and audit trail

### Plan Change Credit Transfer Pattern
**Pattern**: Automatic credit transfer during subscription plan changes
**Implementation**:
- Subscription credits converted to pay-as-you-go credits
- Atomic operations ensure data integrity
- Negative SUBSCRIPTION transactions for removal
- Positive PURCHASE transactions for addition
- Common function ensures consistency across handlers

### Validation and Error Handling Pattern
**Pattern**: Multi-level validation with explicit error handling
**Implementation**:
- Model-level validation with business rule enforcement
- Database constraints for data integrity
- Application-level validation for business logic
- Explicit error types (InsufficientCreditsError)
- Comprehensive error messages for debugging

### Performance Optimization Pattern
**Pattern**: Single-query balance calculations with conditional aggregation
**Implementation**:
- Database-level aggregation reduces query count
- Conditional logic in SQL for expiration filtering
- Strategic indexing for balance calculation queries
- Efficient field configurations for common operations

### Audit Trail Pattern
**Pattern**: Complete transaction logging with descriptive records
**Implementation**:
- All credit movements recorded in CreditTransaction model
- Descriptive transaction descriptions for clarity
- Credit source tracking (subscription vs. pay-as-you-go)
- Service usage linked to credit transactions
- Complete payment history with receipt generation

### Webhook Integration Pattern
**Pattern**: Real-time processing of Stripe events for credit management
**Implementation**:
- Webhook handlers for payment and subscription events
- Automatic credit allocation on subscription renewal
- Plan change processing with credit transfer
- Error handling with graceful fallbacks
- Audit logging for all webhook activities 