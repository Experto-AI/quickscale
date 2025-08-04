# Credit System

## Overview

QuickScale's credit system is a flexible billing and usage tracking system supporting multiple payment models. Users can purchase credits through different methods, and credits are consumed when using services within the platform.

**Source of Truth**: Stripe Products serve as the authoritative source for all pricing and plan information. The system syncs from Stripe to maintain consistency.

## Credit Types

### Pay-as-You-Go Credits
- **Purchase**: One-time payment via Stripe Products (`interval = 'one-time'`)
- **Expiration**: Never expire
- **Consumption Priority**: Consumed **after** subscription credits are exhausted
- **Use Case**: Occasional users or backup credits for subscription users
- **Implementation**: Stripe Products with credit amounts in metadata

### Subscription Credits
- **Purchase**: Monthly subscription via Stripe Products (`interval = 'month'`)
- **Expiration**: Expire at the end of each billing period
- **Consumption Priority**: Consumed **first** before pay-as-you-go credits
- **Renewal**: Automatically allocated each billing cycle
- **Rollover**: Unused credits do NOT roll over to the next period

### Intelligent Expiration Handling

When subscription credits are allocated, the system uses sophisticated expiration logic:

1. **Primary Source**: Uses Stripe's `current_period_end` for precise billing cycle alignment
2. **Intelligent Fallback**: When Stripe billing data is unavailable, uses product interval information
3. **Grace Period**: Small buffer to handle timing discrepancies
4. **Error Recovery**: Graceful handling of API failures or data inconsistencies

## Credit Consumption Logic

### Priority System
1. **Subscription Credits First**: Active subscription credits with earliest expiration
2. **Pay-as-You-Go Second**: Permanent credits after subscription credits exhausted
3. **FIFO Within Type**: First-in, first-out within each credit type

### Transaction Recording
Every credit operation is logged with:
- **User**: Who performed the operation
- **Amount**: Credits added or consumed
- **Type**: Purchase, consumption, allocation, expiration
- **Source**: Stripe payment, subscription renewal, API usage
- **Timestamp**: Precise timing for audit trails
- **Metadata**: Additional context (product ID, service used, etc.)

## Manual Credit Management

### Admin Interface
QuickScale provides comprehensive admin tools for credit management:

#### User Credit Overview
- Current credit balance (subscription + pay-as-you-go)
- Credit transaction history
- Active subscriptions and renewal dates
- Usage patterns and consumption trends

#### Manual Operations
- **Add Credits**: One-time credit additions for support cases
- **Adjust Balance**: Corrections for billing issues
- **Expire Credits**: Force expiration for policy enforcement
- **Transaction Review**: Detailed audit trail access

#### Bulk Operations
- **Import Credits**: CSV-based bulk credit allocation
- **Export Data**: Credit data for external analysis
- **Batch Updates**: Apply changes to multiple users

### Management Commands
```bash
# Add credits to specific user
python manage.py add_credits user@example.com 100 "Support credit adjustment"

# Check user credit status
python manage.py check_credits user@example.com

# Process subscription renewals
python manage.py process_renewals

# Clean expired credits
python manage.py clean_expired_credits
```

## Stripe Integration

### Product Synchronization
The system maintains unidirectional sync from Stripe to QuickScale:

1. **Stripe Products** → QuickScale StripeProduct model
2. **Pricing Information** → Local pricing cache
3. **Subscription Data** → User subscription records
4. **Payment Events** → Credit transactions

### Webhook Handling
Critical Stripe events processed:
- `payment_intent.succeeded` → Add pay-as-you-go credits
- `invoice.payment_succeeded` → Allocate subscription credits
- `customer.subscription.updated` → Update subscription status
- `customer.subscription.deleted` → Handle cancellations

### Error Handling
- **API Failures**: Graceful degradation with retry logic
- **Webhook Delays**: Idempotency handling for duplicate events
- **Data Inconsistencies**: Reconciliation processes and alerts
- **Rate Limiting**: Exponential backoff and queue management

## Security and Compliance

### Data Protection
- **PII Handling**: Minimal personal data storage
- **Encryption**: Sensitive data encrypted at rest
- **Audit Trails**: Complete transaction logging
- **Access Control**: Role-based admin permissions

### Financial Compliance
- **Transaction Integrity**: Atomic operations for credit changes
- **Audit Requirements**: Comprehensive logging for compliance
- **Dispute Handling**: Transaction reversal capabilities
- **Reporting**: Financial summaries and reconciliation

## API Integration

### Credit Check Endpoints
```python
# Check user credits
GET /api/v1/credits/balance/

# Credit transaction history
GET /api/v1/credits/transactions/

# Consume credits for service usage
POST /api/v1/credits/consume/
{
    "amount": 10,
    "service": "ai_generation",
    "metadata": {"model": "gpt-4", "tokens": 1000}
}
```

### Authentication
- **API Keys**: Secure API key authentication
- **Rate Limiting**: Per-user consumption limits
- **Usage Tracking**: Service-specific consumption metrics

## Implementation Details

### Database Schema
```python
class CreditAccount(models.Model):
    user = models.OneToOneField(User)
    subscription_credits = models.PositiveIntegerField(default=0)
    payg_credits = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

class CreditTransaction(models.Model):
    user = models.ForeignKey(User)
    amount = models.IntegerField()  # Positive for additions, negative for consumption
    transaction_type = models.CharField(max_length=20)
    source = models.CharField(max_length=50)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Service Integration Pattern
```python
from credits.services import CreditService

class AIService:
    def generate_content(self, user, prompt):
        # Calculate credit cost
        cost = self.calculate_cost(prompt)
        
        # Check and consume credits
        if CreditService.has_sufficient_credits(user, cost):
            CreditService.consume_credits(
                user=user,
                amount=cost,
                service="ai_generation",
                metadata={"prompt_length": len(prompt)}
            )
            return self.process_generation(prompt)
        else:
            raise InsufficientCreditsError()
```

## Monitoring and Analytics

### Key Metrics
- **Credit Utilization**: Usage patterns by user and service
- **Revenue Tracking**: Subscription vs. pay-as-you-go revenue
- **Churn Analysis**: Credit usage before cancellation
- **Service Costs**: Cost per service operation

### Alerts and Notifications
- **Low Credit Warnings**: Proactive user notifications
- **Failed Payments**: Admin alerts for payment issues
- **Usage Spikes**: Anomaly detection for unusual consumption
- **System Errors**: Credit system health monitoring

This credit system provides flexible billing options while maintaining data integrity, security, and compliance requirements for a production SaaS application.
