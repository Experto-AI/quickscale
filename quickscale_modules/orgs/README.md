# QuickScale Organizations Module

QuickScale organizations provides the foundational multi-tenant data model for organization records, memberships, invitations, and shared tenant ownership, giving later phases a stable base for Solo/SaaS runtime modes, PostgreSQL row-level security, and org-scoped billing.

## Purging an organization

`purge_organization` refuses both destructive execution and `--dry-run` while the organization has a current Stripe-backed subscription. The refusal lists the Stripe subscription IDs; cancel those subscriptions in Stripe before running the command again.
