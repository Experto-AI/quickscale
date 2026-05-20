# QuickScale Billing Module

**Status**: Billing ships in v0.85.0 through the standard QuickScale module workflow. `quickscale.yml` plus env-var-backed runtime settings are authoritative, Stripe keys plus webhook secrets stay environment-only, and billing now depends on the `orgs` module for its org-authoritative ledger/runtime contract.

QuickScale billing is a credits-first org-backed module. Django owns plans, balances, transactions, subscription snapshots, and webhook idempotency records. Stripe is the payment trigger through the direct `stripe` Python SDK; the Django ledger remains the source of truth for credit accounting, and billing requires the `orgs` plus `auth` modules at plan/apply/runtime.

## Current Shipped Surface

- Independently packaged Django module metadata under `quickscale_modules/billing/`
- Five core models: `Plan`, `CreditBalance`, `CreditTransaction`, `Subscription`, and `WebhookEvent`
- Django admin registration for plans, balances, transactions, subscriptions, and webhook events
- Stripe webhook handling for purchases and recurring subscription lifecycle events
- Authenticated JSON APIs for balance, transactions, purchase checkout, subscription checkout, subscription status, subscription cancel, billing portal, and publishable-key discovery
- Module-owned Django pages for canonical org-scoped dashboard/pricing, flat compatibility shims, purchase return routes, subscription return routes, and the billing portal return route
- Manual React adoption guidance so generated frontend files remain user-owned

## Current Boundaries

- Billing requires the `orgs` and `auth` modules at plan/apply/runtime; QuickScale does not support a standalone billing install without those foundations
- Planner/apply now auto-materialize the `orgs` module when billing is selected, and `orgs` continues to auto-materialize default notifications config; auth remains an explicit prerequisite
- In SaaS/org-aware installs, canonical authenticated billing pages and APIs are org-scoped under `/orgs/<slug>/...`; flat authenticated billing routes remain compatibility shims for Solo mode and older non-org callers
- `GET /api/billing/plans/` is intentionally recurring-only; one-time credit packs are purchaseable but do not currently ship through a public catalog endpoint
- Checkout success, cancel, and portal return URLs are server-owned; callers may not supply them in API requests
- Stripe keys are resolved from environment variables at runtime and are never stored in the database

## Credits-First Domain Contract

- `Plan` stores QuickScale-owned display metadata plus the authoritative Stripe Price reference used for checkout validation
- `CreditBalance` tracks the current authoritative per-organization credit balance; nullable user links remain provenance / compatibility only
- `CreditTransaction` records each credit mutation with balance snapshots and optional Stripe reference metadata
- `Subscription` stores the local snapshot of recurring billing state keyed authoritatively to the organization; nullable user links remain provenance / compatibility only
- `WebhookEvent` is the transport-level idempotency gate for Stripe webhook processing
- `debit_user` is the approved service API for credit consumption

## Explicit Non-Goals For The Current Contract

- No Stripe catalog authoring from Django admin
- No coupons, tax/VAT workflows, metered billing, or custom invoice-history UI
- No seat billing, seat-limit fields, or seat-based enforcement yet
- No rewrites of user-owned frontend files

## React Integration Guide

This phase documents how to wire the billing module into a generated React frontend without asking QuickScale to mutate user-owned frontend files. The module already ships Django mount points and JSON APIs; your React app owns how those APIs are consumed.

### Integration Assumptions

- Use Django session authentication for authenticated billing routes.
- Send CSRF tokens on all authenticated `POST` requests.
- Treat the backend as the source of truth for redirect targets. Only send `plan_slug` for checkout creation and an empty JSON body for cancel and portal creation.
- Keep one-time purchase catalog data project-owned for now. The shipped `plans` endpoint only exposes active recurring plans.
- Treat transaction pagination as fixed-size, page-number based pagination. The API always uses 25 rows per page and ignores client-supplied `page_size` values.

### API Contract

Canonical SaaS callers should use the org-scoped `/orgs/<slug>/api/billing/...` endpoints. The flat `/api/billing/...` routes documented below remain compatibility shims for Solo mode and older non-org integrations.

| Route | Method | Auth | Request | Success contract | Notes |
| --- | --- | --- | --- | --- | --- |
| `/api/billing/config/` | `GET` | Session auth | None | `{"publishable_key": "pk_test_..."}` | Returns only the publishable key. Returns `500` with `{"error": "Stripe publishable key is not configured in the runtime environment."}` when missing. |
| `/api/billing/plans/` | `GET` | Public | None | `[{"name": "Starter Monthly", "slug": "starter-monthly", "credits_per_period": 100, "price_cents": 1900, "currency": "usd", "billing_interval": "monthly"}]` | Returns active recurring plans only. One-time plans stay out of this catalog. |
| `/api/billing/balance/` | `GET` | Session auth | None | `{"balance": 125, "updated_at": "2026-05-16T12:00:00Z"}` | Creates a zero-balance row on first read. |
| `/api/billing/transactions/?page=2` | `GET` | Session auth | `page` query param only | `[{"id": 42, "amount": 125, "transaction_type": "purchase", "description": "Current user purchase", "balance_after": 125, "created_at": "2026-05-16T12:00:00Z"}]` | Ordered newest-first. Fixed page size of `25`; client `page_size` overrides are ignored. |
| `/api/billing/purchase/checkout/` | `POST` | Session auth + CSRF | `{"plan_slug": "credits-pack"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | Rejects caller-supplied `success_url` and `cancel_url`. |
| `/api/billing/subscription/` | `GET` | Session auth | None | `{"plan": {"name": "Starter Monthly", "slug": "starter-monthly", "credits_per_period": 100, "price_cents": 1900, "currency": "usd", "billing_interval": "monthly"}, "status": "active", "checkout_expires_at": null, "current_period_start": "2026-05-16T12:00:00Z", "current_period_end": "2026-06-15T12:00:00Z"}` | Returns `404` with `{"error": "Current subscription not found."}` when no current recurring row exists. |
| `/api/billing/subscription/checkout/` | `POST` | Session auth + CSRF | `{"plan_slug": "starter-monthly"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | Rejects caller-supplied `success_url` and `cancel_url`. Blocks if a current recurring subscription already exists. |
| `/api/billing/subscription/cancel/` | `POST` | Session auth + CSRF | `{}` | `204 No Content` | Rejects caller-supplied `return_url`. Schedules `cancel_at_period_end=True`. |
| `/api/billing/portal/` | `POST` | Session auth + CSRF | `{}` | `{"portal_url": "https://billing.stripe.com/..."}` | Rejects caller-supplied `return_url`. Uses the module-owned `billing/portal/return/` route. |

### Module-Owned Billing Pages

The module already ships Django pages that you can either use directly or treat as mount points for your React frontend. In SaaS/org-aware installs, canonical authenticated pages are org-scoped and the flat authenticated route remains a compatibility shim:

- `GET /orgs/<slug>/billing/dashboard/` renders the canonical authenticated billing page with `<div id="billing-root" data-view="dashboard">`
- `GET /orgs/<slug>/billing/pricing/` renders the canonical org-scoped pricing page with `<div id="billing-root" data-view="pricing">`
- `GET /billing/dashboard/` remains available as a compatibility redirect for Solo mode and older non-org callers
- `GET /billing/pricing/` remains the flat public pricing page
- `GET /billing/purchase/success/` and `GET /billing/purchase/cancel/` render purchase return pages
- `GET /billing/subscription/success/` and `GET /billing/subscription/cancel/` render subscription return pages
- `GET /billing/portal/return/` renders the Stripe billing-portal return page

### Shared React Helpers

Start with one typed fetch wrapper, one CSRF helper, and one runtime Stripe bootstrap.

```ts
import { loadStripe, type Stripe } from "@stripe/stripe-js";

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

function getCsrfToken(): string {
	const cookie = document.cookie
		.split("; ")
		.find((entry) => entry.startsWith("csrftoken="));
	return cookie ? decodeURIComponent(cookie.split("=")[1] ?? "") : "";
}

async function billingFetch<T>(input: string, init: RequestInit = {}): Promise<T> {
	const response = await fetch(input, {
		credentials: "include",
		headers: {
			"Content-Type": "application/json",
			...(init.method && init.method !== "GET"
				? { "X-CSRFToken": getCsrfToken() }
				: {}),
			...(init.headers ?? {}),
		},
		...init,
	});

	if (response.status === 204) {
		return undefined as T;
	}

	const payload = (await response.json()) as
		| { error?: string; errors?: Record<string, string[]> }
		| T;

	if (!response.ok) {
		if (typeof payload === "object" && payload !== null && "error" in payload) {
			throw new Error(payload.error || "Billing request failed.");
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

### `loadStripe()` Redirect Pattern

QuickScale returns Stripe-hosted URLs instead of a client-created Checkout Session ID. Keep `loadStripe()` in your React app as the one place where publishable-key configuration is validated, then redirect to the server-issued URL.

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

This keeps Stripe bootstrap logic in one place while preserving the module's server-owned redirect contract.

### TanStack Query Patterns

Use polling for balance, page-number query keys for transactions, and regular invalidation after subscription changes or return-page refreshes.

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

### Component Patterns

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

### Environment Variable Wiring

Keep Stripe key wiring runtime-owned. Do not hardcode the publishable key in the React source tree.

Backend environment variables:

```bash
export QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR=STRIPE_PUBLISHABLE_KEY
export QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR=STRIPE_SECRET_KEY
export QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR=QUICKSCALE_BILLING_WEBHOOK_SECRET

export STRIPE_PUBLISHABLE_KEY=pk_live_or_test_...
export STRIPE_SECRET_KEY=sk_live_or_test_...
export QUICKSCALE_BILLING_WEBHOOK_SECRET=whsec_...
```

Frontend runtime wiring:

- Load `/api/billing/config/` after the user is authenticated.
- Map the returned `publishable_key` into your app's runtime config shape as `VITE_STRIPE_PUBLISHABLE_KEY` if you want one consistent frontend config name.
- Feed that runtime value into `loadStripe()` through `loadBillingRuntimeConfig()` rather than storing a checked-in `.env` value.

### Recommended shadcn/ui Surfaces

- `CreditBalanceCard`: `Card`, `Skeleton`
- `PricingPage`: `Tabs`, `Card`, `Badge`, `Button`
- `PurchaseButton`: `Button`, spinner icon such as `Loader2`
- `SubscriptionStatusCard`: `Card`, `Badge`, `Alert`, `Button`
- `TransactionHistory`: `Table`, `ScrollArea`, `Button`

## Distribution Notes

Billing ships through the standard QuickScale module packaging and split-branch workflow. The module manifest declares `required_modules: [orgs]`, and the package metadata declares `quickscale-module-orgs` so standalone package consumers and QuickScale planner/apply flows advertise the same dependency contract. Follow-on roadmap work may tighten release evidence or adjacent docs, but this README describes the current shipped module contract.

See [Technical Roadmap](../../docs/technical/roadmap.md) for the full v0.85.0 implementation plan.
