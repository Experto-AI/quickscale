# QuickScale Billing Module

Credits-first, organization-backed billing for QuickScale projects. Django owns plans,
balances, transactions, purchase Checkout lifecycle reservations, subscription snapshots, and
webhook idempotency records. Stripe is the payment trigger through the direct `stripe` Python
SDK; the Django ledger remains the source of truth for credit accounting. Billing requires the
`orgs` and `auth` modules at plan/apply/runtime.

## Overview

- Independently packaged Django module metadata under `quickscale_modules/billing/`.
- Six core models: `Plan`, `CreditBalance`, `CreditTransaction`, `PurchaseCheckout`,
  `Subscription`, and `WebhookEvent`.
- Django admin registration for plans, balances, transactions, purchase Checkout reservations,
  subscriptions, and webhook events.
- Stripe webhook handling for purchases and recurring subscription lifecycle events.
- Authenticated JSON APIs for balance, transactions, purchase checkout, subscription checkout,
  subscription status, subscription cancel, billing portal, and publishable-key discovery.
- Module-owned Django pages for flat dashboard and pricing routes in both Solo and SaaS modes,
  purchase return routes, subscription return routes, and the billing portal return route.
- Manual React adoption guidance, so generated frontend files remain user-owned.

Boundaries:

- Billing requires the `orgs` and `auth` modules at plan/apply/runtime; there is no standalone
  billing install without those foundations.
- Planner/apply auto-materializes `orgs` when billing is selected, and `orgs` auto-materializes
  `notifications`; auth remains an explicit prerequisite.
- All billing pages and APIs use flat routes (`billing/...`, `api/billing/...`) in both Solo and
  SaaS modes; no org-scoped billing URL tree exists.
- `GET /api/billing/plans/` is intentionally recurring-only; one-time credit packs are
  purchaseable but do not ship through a public catalog endpoint.
- Checkout success, cancel, and portal return URLs are server-owned; callers may not supply
  them in API requests.
- Stripe keys are resolved from environment variables at runtime and are never stored in the
  database.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_BILLING_ENABLED` | Enable the billing runtime and Stripe-backed services. |
| `publishable_key_env_var` | string | `STRIPE_PUBLISHABLE_KEY` | `QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR` | Environment-variable name containing the Stripe publishable key used by billing checkout flows. |
| `secret_key_env_var` | string | `STRIPE_SECRET_KEY` | `QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR` | Environment-variable name containing the Stripe secret key for server-side API calls. |
| `webhook_secret_env_var` | string | `QUICKSCALE_BILLING_WEBHOOK_SECRET` | `QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR` | Environment-variable name containing the Stripe webhook signing secret. |
| `billing_currency` | string | `usd` | `QUICKSCALE_BILLING_CURRENCY` | ISO 4217 billing currency code used for plan metadata and Checkout validation. |
| `api_rate_limit` | string | `30/hour` | `QUICKSCALE_BILLING_API_RATE_LIMIT` | Throttle rate per client for billing's Stripe-calling checkout and portal endpoints. Format: `<count>/<period>`. |

Backend environment variables:

```bash
export QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR=STRIPE_PUBLISHABLE_KEY
export QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR=STRIPE_SECRET_KEY
export QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR=QUICKSCALE_BILLING_WEBHOOK_SECRET

export STRIPE_PUBLISHABLE_KEY=pk_live_or_test_...
export STRIPE_SECRET_KEY=sk_live_or_test_...
export QUICKSCALE_BILLING_WEBHOOK_SECRET=whsec_...
```

The `*_env_var` options name the environment variables that carry the real credentials; only
the credential values themselves are deploy-time environment variables. Keep Stripe key wiring
runtime-owned and never hardcode the publishable key in the frontend source tree.

## Public surface

### Credits-first domain contract

- `Plan` stores QuickScale-owned display metadata plus the authoritative Stripe Price reference
  used for checkout validation.
- `CreditBalance` tracks the current authoritative per-organization credit balance; nullable
  user links remain provenance / compatibility only.
- `CreditTransaction` records each credit mutation with balance snapshots and optional Stripe
  reference metadata.
- `PurchaseCheckout` records one-time Checkout lifecycle state so account deletion and
  organization purge can reconcile or refuse live provider sessions; Stripe metadata and
  idempotency keys correlate completed or expired sessions even when the provider-create
  response is lost.
- `Subscription` stores the local snapshot of recurring billing state keyed authoritatively to
  the organization; recurring Checkout uses the same reservation-reference and response-loss
  recovery contract, while nullable user links remain provenance / compatibility only.
- `WebhookEvent` is the transport-level idempotency gate for Stripe webhook processing.
- `debit_user` is the approved service API for credit consumption.

### Account-deletion capability

`QuickscaleBillingConfig` declares billing's account-deletion handler through the Module
Conventions rule 4 `account_deletion_handlers` capability: account deletion collects every
installed handler and drives Stripe purchase-checkout reconciliation, subscription-checkout
reconciliation for the organizations whose subscriptions the deletion cancels, cancellation
with compensation, provider mutation locking, and provenance detachment through it, so no
consumer imports billing's services or names its label.

### API contract

All billing API routes are flat (`api/billing/...`) and used in both Solo and SaaS modes. The
organization is resolved from the session / `request.org` contract established by middleware,
not from a URL slug. Every error answers the shared
`{"error": {"code", "message", "fields"}}` shape (`fields` only for validation errors), and a
disabled billing runtime answers `404`.

| Route | Method | Auth | Request | Success contract | Notes |
| --- | --- | --- | --- | --- | --- |
| `api/billing/config/` | `GET` | Session auth | None | `{"publishable_key": "pk_test_..."}` | Returns only the publishable key. Returns `500` with `{"error": {"code": "configuration_error", "message": "Stripe publishable key is not configured in the runtime environment."}}` when missing. |
| `api/billing/plans/` | `GET` | Public | None | `[{"name": "Starter Monthly", "slug": "starter-monthly", "credits_per_period": 100, "price_cents": 1900, "currency": "usd", "billing_interval": "monthly"}]` | Returns active recurring plans only. One-time plans stay out of this catalog. |
| `api/billing/balance/` | `GET` | Session auth | None | `{"balance": 0, "updated_at": null}` | A missing balance is returned as a read-only zero snapshot without creating a row. Persisted balances include their `updated_at` timestamp. |
| `api/billing/transactions/?page=2` | `GET` | Session auth | `page` query param only | `[{"id": 42, "amount": 125, "transaction_type": "purchase", "description": "Current user purchase", "balance_after": 125, "created_at": "2026-05-16T12:00:00Z"}]` | Ordered newest-first. Fixed page size of `25`; client `page_size` overrides are ignored. |
| `api/billing/purchase/checkout/` | `POST` | Session auth + CSRF | `{"plan_slug": "credits-pack"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | Rejects caller-supplied `success_url` and `cancel_url`. |
| `api/billing/subscription/` | `GET` | Session auth | None | `{"plan": {...}, "status": "active", "checkout_expires_at": null, "current_period_start": "...", "current_period_end": "..."}` | Returns `404` with `{"error": {"code": "not_found", "message": "Current subscription not found."}}` when no current recurring row exists. |
| `api/billing/subscription/checkout/` | `POST` | Session auth + CSRF | `{"plan_slug": "starter-monthly"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | Rejects caller-supplied `success_url` and `cancel_url`. Blocks if a current recurring subscription already exists. |
| `api/billing/subscription/cancel/` | `POST` | Session auth + CSRF | `{}` | `204 No Content` | Rejects caller-supplied `return_url`. Schedules `cancel_at_period_end=True`. |
| `api/billing/portal/` | `POST` | Session auth + CSRF | `{}` | `{"portal_url": "https://billing.stripe.com/..."}` | Rejects caller-supplied `return_url`. Uses the module-owned `billing/portal/return/` route. |

### Module-owned billing pages

The module ships Django pages that you can either use directly or treat as mount points for
your React frontend. All billing routes are flat in both Solo and SaaS modes:

- `GET billing/dashboard/` renders the authenticated billing page with
  `<div id="billing-root" data-view="dashboard">`.
- `GET billing/pricing/` renders the pricing page with `<div id="billing-root" data-view="pricing">`.
- `GET billing/purchase/success/` and `GET billing/purchase/cancel/` render purchase return
  pages.
- `GET billing/subscription/success/` and `GET billing/subscription/cancel/` render subscription
  return pages.
- `GET billing/portal/return/` renders the Stripe billing-portal return page.

### React integration guide

This module documents how to wire billing into a generated React frontend without asking
QuickScale to mutate user-owned frontend files. The module ships Django mount points and JSON
APIs; your React app owns how those APIs are consumed.

Integration assumptions:

- Use Django session authentication for authenticated billing routes.
- Send CSRF tokens on all authenticated `POST` requests.
- Treat the backend as the source of truth for redirect targets. Only send `plan_slug` for
  checkout creation and an empty JSON body for cancel and portal creation.
- Keep one-time purchase catalog data project-owned for now. The shipped `plans` endpoint only
  exposes active recurring plans.
- Treat transaction pagination as fixed-size, page-number based pagination. The API always uses
  25 rows per page and ignores client-supplied `page_size` values.

Start with one typed fetch wrapper, one CSRF helper, and one runtime Stripe bootstrap.

```ts
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import { getCsrfToken } from "@/lib/csrf";

type BillingConfig = { publishable_key: string };
type BillingBalance = { balance: number; updated_at: string | null };
type BillingPlan = {
  name: string;
  slug: string;
  credits_per_period: number;
  price_cents: number;
  currency: string;
  billing_interval: "monthly" | "yearly";
};
type BillingSubscription = {
  plan: BillingPlan;
  status:
    | "incomplete"
    | "incomplete_expired"
    | "trialing"
    | "active"
    | "past_due"
    | "canceled"
    | "unpaid"
    | "paused";
  checkout_expires_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
};
type CreditTransaction = {
  id: number;
  amount: number;
  transaction_type: string;
  description: string;
  balance_after: number;
  created_at: string;
};

async function billingFetch<T>(input: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const method = init.method?.toUpperCase() ?? "GET";
  if (method !== "GET" && method !== "HEAD" && !headers.has("X-CSRFToken")) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  const response = await fetch(input, {
    credentials: "include",
    ...init,
    headers,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = (await response.json()) as
    | {
        error?: {
          code: string;
          message: string;
          fields?: Record<string, string[]>;
        };
      }
    | T;

  if (!response.ok) {
    if (typeof payload === "object" && payload !== null && "error" in payload && payload.error) {
      throw new Error(payload.error.message || "Billing request failed.");
    }
    throw new Error(JSON.stringify(payload));
  }

  return payload as T;
}

export async function loadBillingRuntimeConfig(): Promise<{
  VITE_STRIPE_PUBLISHABLE_KEY: string;
}> {
  const { publishable_key } = await billingFetch<BillingConfig>(
    "/api/billing/config/",
  );
  return { VITE_STRIPE_PUBLISHABLE_KEY: publishable_key };
}

let stripePromise: Promise<Stripe | null> | null = null;

export async function getStripe(): Promise<Stripe | null> {
  if (!stripePromise) {
    stripePromise = loadBillingRuntimeConfig().then((config) =>
      loadStripe(config.VITE_STRIPE_PUBLISHABLE_KEY),
    );
  }
  return stripePromise;
}

export function fetchBalance() {
  return billingFetch<BillingBalance>("/api/billing/balance/");
}

export function fetchRecurringPlans() {
  return billingFetch<BillingPlan[]>("/api/billing/plans/");
}

export function fetchTransactions(page = 1) {
  return billingFetch<CreditTransaction[]>(`/api/billing/transactions/?page=${page}`);
}

export async function fetchCurrentSubscription() {
  try {
    return await billingFetch<BillingSubscription>("/api/billing/subscription/");
  } catch (error) {
    if (error instanceof Error && error.message === "Current subscription not found.") {
      return null;
    }
    throw error;
  }
}

export async function createPurchaseCheckout(planSlug: string) {
  return billingFetch<{ checkout_url: string }>("/api/billing/purchase/checkout/", {
    method: "POST",
    body: JSON.stringify({ plan_slug: planSlug }),
  });
}

export async function createSubscriptionCheckout(planSlug: string) {
  return billingFetch<{ checkout_url: string }>(
    "/api/billing/subscription/checkout/",
    {
      method: "POST",
      body: JSON.stringify({ plan_slug: planSlug }),
    },
  );
}

export async function cancelCurrentSubscription() {
  return billingFetch<void>("/api/billing/subscription/cancel/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function createBillingPortalSession() {
  return billingFetch<{ portal_url: string }>("/api/billing/portal/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}
```

QuickScale returns Stripe-hosted URLs instead of a client-created Checkout Session ID. Keep
`loadStripe()` in your React app as the one place where publishable-key configuration is
validated, then redirect to the server-issued URL:

```ts
async function redirectToStripeHostedUrl(
  getUrl: () => Promise<{ checkout_url?: string; portal_url?: string }>,
) {
  await getStripe();
  const payload = await getUrl();
  const targetUrl = payload.checkout_url ?? payload.portal_url;

  if (!targetUrl) {
    throw new Error("Billing endpoint did not return a redirect URL.");
  }

  window.location.assign(targetUrl);
}

export function startPurchaseRedirect(planSlug: string) {
  return redirectToStripeHostedUrl(() => createPurchaseCheckout(planSlug));
}

export function startSubscriptionRedirect(planSlug: string) {
  return redirectToStripeHostedUrl(() => createSubscriptionCheckout(planSlug));
}

export function startBillingPortalRedirect() {
  return redirectToStripeHostedUrl(() => createBillingPortalSession());
}
```

Use TanStack Query with polling for balance, page-number query keys for transactions, and
regular invalidation after subscription changes or return-page refreshes:

```ts
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

export function useBillingBalance() {
  return useQuery({
    queryKey: ["billing", "balance"],
    queryFn: fetchBalance,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useBillingTransactions(page: number) {
  return useQuery({
    queryKey: ["billing", "transactions", page],
    queryFn: () => fetchTransactions(page),
    placeholderData: keepPreviousData,
  });
}

export function useCurrentSubscription() {
  return useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: fetchCurrentSubscription,
  });
}

export function useSubscriptionCancel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: cancelCurrentSubscription,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["billing", "subscription"] }),
        queryClient.invalidateQueries({ queryKey: ["billing", "balance"] }),
        queryClient.invalidateQueries({ queryKey: ["billing", "transactions"] }),
      ]);
    },
  });
}
```

Component patterns and the recommended shadcn/ui surfaces:

- **Credit balance widget**: a `Card` with a `Skeleton` fallback; poll the balance query because
  webhook-driven credit changes can happen outside the current tab.
- **Pricing page**: `Tabs`, `Card`, `Badge`, and `Button`; fetch recurring plans from
  `api/billing/plans/` and optionally merge project-owned one-time pack metadata on the same
  screen.
- **Purchase button**: a `Button` with spinner state; it only needs a `planSlug` because the
  backend owns both redirect URLs.
- **Subscription status**: `Card`, `Badge`, `Alert`, and `Button`; render `null` when there is
  no active recurring row, use `api/billing/portal/` for billing management, and
  `api/billing/subscription/cancel/` to schedule period-end cancellation.
- **Transaction history**: `Table`, `ScrollArea`, and `Button`; the API returns a plain list
  without total-count metadata, so use page-number state and infer whether another page exists
  from the fixed page size.

Examples:

#### 1. CreditBalance widget

Use a shadcn/ui `Card` with a `Skeleton` fallback. Poll the balance query because webhook-driven credit changes can happen outside the current tab.

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function CreditBalanceCard() {
	const { data, isPending } = useBillingBalance();

	return (
		<Card>
			<CardHeader>
				<CardTitle>Credit balance</CardTitle>
			</CardHeader>
			<CardContent>
				{isPending ? (
					<Skeleton className="h-8 w-24" />
				) : (
					<>
						<div className="text-3xl font-semibold">{data?.balance ?? 0}</div>
						<p className="text-sm text-muted-foreground">
							Updated {data?.updated_at ? new Date(data.updated_at).toLocaleString() : "just now"}
						</p>
					</>
				)}
			</CardContent>
		</Card>
	);
}
```

#### 2. PricingPage

Use shadcn/ui `Tabs`, `Card`, `Badge`, and `Button`. Fetch recurring plans from `/api/billing/plans/`, then optionally merge project-owned one-time pack metadata if you want purchase cards on the same screen.

```tsx
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ONE_TIME_PACKS = [
	{ slug: "credits-pack", name: "Credits Pack", credits: 250, priceCents: 4900 },
];

export function PricingPage() {
	const plansQuery = useQuery({
		queryKey: ["billing", "plans"],
		queryFn: fetchRecurringPlans,
	});

	return (
		<Tabs defaultValue="subscriptions" className="space-y-6">
			<TabsList>
				<TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
				<TabsTrigger value="credit-packs">Credit packs</TabsTrigger>
			</TabsList>

			<TabsContent value="subscriptions" className="grid gap-4 md:grid-cols-2">
				{plansQuery.data?.map((plan) => (
					<Card key={plan.slug}>
						<CardHeader>
							<div className="flex items-center justify-between gap-3">
								<CardTitle>{plan.name}</CardTitle>
								<Badge variant="secondary">{plan.billing_interval}</Badge>
							</div>
						</CardHeader>
						<CardContent>
							<p>{plan.credits_per_period} credits per period</p>
							<p className="text-2xl font-semibold">
								{(plan.price_cents / 100).toLocaleString(undefined, {
									style: "currency",
									currency: plan.currency.toUpperCase(),
								})}
							</p>
						</CardContent>
						<CardFooter>
							<Button onClick={() => startSubscriptionRedirect(plan.slug)}>
								Subscribe
							</Button>
						</CardFooter>
					</Card>
				))}
			</TabsContent>

			<TabsContent value="credit-packs" className="grid gap-4 md:grid-cols-2">
				{ONE_TIME_PACKS.map((pack) => (
					<Card key={pack.slug}>
						<CardHeader>
							<CardTitle>{pack.name}</CardTitle>
						</CardHeader>
						<CardContent>
							<p>{pack.credits} one-time credits</p>
						</CardContent>
						<CardFooter>
							<PurchaseButton planSlug={pack.slug}>Buy credits</PurchaseButton>
						</CardFooter>
					</Card>
				))}
			</TabsContent>
		</Tabs>
	);
}
```

#### 3. PurchaseButton

Use a shadcn/ui `Button` plus spinner state. The button only needs a `planSlug`; the backend owns both redirect URLs.

```tsx
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PurchaseButton({
	planSlug,
	children,
}: {
	planSlug: string;
	children: React.ReactNode;
}) {
	const [isLoading, setIsLoading] = useState(false);

	return (
		<Button
			disabled={isLoading}
			onClick={async () => {
				try {
					setIsLoading(true);
					await startPurchaseRedirect(planSlug);
				} finally {
					setIsLoading(false);
				}
			}}
		>
			{isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
			{children}
		</Button>
	);
}
```

#### 4. SubscriptionStatus

Use a shadcn/ui `Card`, `Badge`, `Alert`, and `Button`. Render `null` when there is no active recurring row, call `/api/billing/portal/` for billing management, and call `/api/billing/subscription/cancel/` to schedule period-end cancellation.

```tsx
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SubscriptionStatusCard() {
	const subscriptionQuery = useCurrentSubscription();
	const cancelMutation = useSubscriptionCancel();

	if (!subscriptionQuery.data) {
		return null;
	}

	const subscription = subscriptionQuery.data;

	return (
		<Card>
			<CardHeader>
				<div className="flex items-center justify-between gap-3">
					<CardTitle>{subscription.plan.name}</CardTitle>
					<Badge>{subscription.status}</Badge>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				<Alert>
					<AlertTitle>Current period</AlertTitle>
					<AlertDescription>
						{subscription.current_period_start} to {subscription.current_period_end}
					</AlertDescription>
				</Alert>

				<div className="flex flex-wrap gap-3">
					<Button onClick={() => void startBillingPortalRedirect()}>
						Open billing portal
					</Button>
					<Button
						variant="outline"
						disabled={cancelMutation.isPending}
						onClick={() => cancelMutation.mutate()}
					>
						Cancel at period end
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}
```

#### 5. TransactionHistory

Use shadcn/ui `Table`, `ScrollArea`, and `Button`. Because the API returns a plain list without total-count metadata, use page-number state and infer whether another page exists from the fixed page size.

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

const TRANSACTION_PAGE_SIZE = 25;

export function TransactionHistory() {
	const [page, setPage] = useState(1);
	const transactionsQuery = useBillingTransactions(page);
	const hasNextPage = (transactionsQuery.data?.length ?? 0) === TRANSACTION_PAGE_SIZE;

	return (
		<div className="space-y-4">
			<ScrollArea className="rounded-md border">
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Date</TableHead>
							<TableHead>Type</TableHead>
							<TableHead>Description</TableHead>
							<TableHead>Amount</TableHead>
							<TableHead>Balance After</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{transactionsQuery.data?.map((transaction) => (
							<TableRow key={transaction.id}>
								<TableCell>
									{new Date(transaction.created_at).toLocaleString()}
								</TableCell>
								<TableCell>{transaction.transaction_type}</TableCell>
								<TableCell>{transaction.description}</TableCell>
								<TableCell>{transaction.amount}</TableCell>
								<TableCell>{transaction.balance_after}</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			</ScrollArea>

			<div className="flex items-center justify-between">
				<Button
					variant="outline"
					disabled={page === 1}
					onClick={() => setPage((currentPage) => currentPage - 1)}
				>
					Previous
				</Button>
				<span className="text-sm text-muted-foreground">Page {page}</span>
				<Button
					variant="outline"
					disabled={!hasNextPage}
					onClick={() => setPage((currentPage) => currentPage + 1)}
				>
					Next
				</Button>
			</div>
		</div>
	);
}
```

Frontend runtime wiring: load `api/billing/config/` after the user is authenticated, map the
returned `publishable_key` into your runtime config shape as `VITE_STRIPE_PUBLISHABLE_KEY` if
you want one consistent frontend config name, and feed that runtime value into `loadStripe()`
rather than storing a checked-in `.env` value.

## URLs

`quickscale apply` mounts the module at the project root; the module's paths are:

| URL name | Path | Purpose |
|----------|------|---------|
| `quickscale_billing:billing-config` | `api/billing/config/` | Publishable-key discovery |
| `quickscale_billing:subscription-plans` | `api/billing/plans/` | Active recurring plan catalog |
| `quickscale_billing:credit-balance` | `api/billing/balance/` | Credit balance |
| `quickscale_billing:credit-transactions` | `api/billing/transactions/` | Credit transactions (paged) |
| `quickscale_billing:purchase-checkout` | `api/billing/purchase/checkout/` | One-time purchase Checkout |
| `quickscale_billing:subscription-detail` | `api/billing/subscription/` | Current subscription |
| `quickscale_billing:subscription-checkout` | `api/billing/subscription/checkout/` | Recurring Checkout |
| `quickscale_billing:subscription-cancel-current` | `api/billing/subscription/cancel/` | Schedule period-end cancellation |
| `quickscale_billing:billing-portal-session` | `api/billing/portal/` | Stripe billing portal session |
| `quickscale_billing:billing-dashboard` | `billing/dashboard/` | Billing dashboard page |
| `quickscale_billing:pricing-page` | `billing/pricing/` | Pricing page |
| `quickscale_billing:purchase-success` | `billing/purchase/success/` | Purchase return (success) |
| `quickscale_billing:purchase-cancel` | `billing/purchase/cancel/` | Purchase return (cancel) |
| `quickscale_billing:subscription-success` | `billing/subscription/success/` | Subscription return (success) |
| `quickscale_billing:subscription-cancel` | `billing/subscription/cancel/` | Subscription return (cancel) |
| `quickscale_billing:portal-return` | `billing/portal/return/` | Billing portal return |
| `quickscale_billing:stripe-webhook` | `billing/webhooks/stripe/` | Stripe webhook endpoint |

## Management commands

This module ships no management commands.

## Operations

### Stripe API version contract

Billing targets the Stripe API version `2026-06-24.dahlia` — the version the pinned `stripe`
SDK (`>=15.3.1,<16.0.0`) ships. The runtime sets that version on the SDK before every call,
and every webhook event must report the same named release: `handle_stripe_event` rejects an
event from a different named release with `BillingConfigurationError`, which the webhook view
answers with `500` so Stripe retries, and it logs each event's reported version.

The Stripe webhook endpoint for this module **must** use API version `2026-06-24.dahlia` and
point at `/billing/webhooks/stripe/`.

**Upgrade note:** a deployment whose webhook endpoint is on an older API version stops
processing all billing webhooks (`500`s) until the endpoint is recreated at
`2026-06-24.dahlia`. Events refused under the old version are not credited automatically, so
reconcile them once the endpoint is on `2026-06-24.dahlia`: resend the event to that endpoint
(Stripe Dashboard **Resend**, or `stripe events resend <event_id> --webhook-endpoint=<new_endpoint_id>`,
up to 30 days) and confirm it is accepted; when an event is still refused or is outside the
resend window, credit the affected invoice once through the module's `credit_user` service from
a Django shell so the balance and ledger stay consistent.

### Deployment notes

Billing ships through the standard QuickScale module packaging and split-branch workflow. The
module manifest declares `required_modules: [orgs]` for planner/apply dependency enforcement.
Follow-on roadmap work may tighten release evidence or adjacent docs; the module contract above
is the current shipped surface.

## Extending

- **Service API**: `debit_user` is the approved service API for credit consumption; the module
  also exposes `credit_user`, `handle_stripe_event`, and the reconciliation helpers in
  `services.py` for project-owned integration code.
- **Explicit non-goals** for the current contract: no Stripe catalog authoring from the Django
  admin, no coupons, tax/VAT workflows, metered billing, or custom invoice-history UI, no seat
  billing or seat-based enforcement, and no rewrites of user-owned frontend files.
- **Roadmap**: see the [technical roadmap](../../docs/technical/roadmap.md) for active
  billing work.
