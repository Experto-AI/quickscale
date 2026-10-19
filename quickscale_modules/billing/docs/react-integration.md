# Billing React Integration Examples

Example TypeScript wiring for the billing JSON APIs in a generated `showcase_react` frontend. Integration assumptions and the API contract: [billing README](../README.md#react-integration-guide).

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
    "/billing/api/config/",
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
  return billingFetch<BillingBalance>("/billing/api/balance/");
}

export async function fetchRecurringPlans() {
  // The catalog is paged (plans_per_page, default 25). A page past the last
  // one answers an empty list, so following pages until an empty batch
  // collects the whole catalog without knowing the configured size.
  const plans: BillingPlan[] = [];
  for (let page = 1; ; page += 1) {
    const batch = await billingFetch<BillingPlan[]>(
      `/billing/api/plans/?page=${page}`,
    );
    if (batch.length === 0) break;
    plans.push(...batch);
  }
  return plans;
}

export function fetchTransactions(page = 1) {
  return billingFetch<CreditTransaction[]>(`/billing/api/transactions/?page=${page}`);
}

export async function fetchCurrentSubscription() {
  try {
    return await billingFetch<BillingSubscription>("/billing/api/subscription/");
  } catch (error) {
    if (error instanceof Error && error.message === "Current subscription not found.") {
      return null;
    }
    throw error;
  }
}

export async function createPurchaseCheckout(planSlug: string) {
  return billingFetch<{ checkout_url: string }>("/billing/api/purchase/checkout/", {
    method: "POST",
    body: JSON.stringify({ plan_slug: planSlug }),
  });
}

export async function createSubscriptionCheckout(planSlug: string) {
  return billingFetch<{ checkout_url: string }>(
    "/billing/api/subscription/checkout/",
    {
      method: "POST",
      body: JSON.stringify({ plan_slug: planSlug }),
    },
  );
}

export async function cancelCurrentSubscription() {
  return billingFetch<void>("/billing/api/subscription/cancel/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function createBillingPortalSession() {
  return billingFetch<{ portal_url: string }>("/billing/api/portal/", {
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
  `billing/api/plans/` and optionally merge project-owned one-time pack metadata on the same
  screen. The catalog is paged by `plans_per_page` (default `25`); the `fetchRecurringPlans`
  helper follows pages until an empty response (a page past the end answers the empty list), so
  the UI shows the whole catalog.
- **Purchase button**: a `Button` with spinner state; it only needs a `planSlug` because the
  backend owns both redirect URLs.
- **Subscription status**: `Card`, `Badge`, `Alert`, and `Button`; render `null` when there is
  no active recurring row, use `billing/api/portal/` for billing management, and
  `billing/api/subscription/cancel/` to schedule period-end cancellation.
- **Transaction history**: `Table`, `ScrollArea`, and `Button`; the API returns a plain list
  without total-count metadata, so use page-number state and infer whether another page exists
  from the configured page size (`QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE`).

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

Use shadcn/ui `Tabs`, `Card`, `Badge`, and `Button`. Fetch recurring plans from `/billing/api/plans/`, then optionally merge project-owned one-time pack metadata if you want purchase cards on the same screen.

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

Use a shadcn/ui `Card`, `Badge`, `Alert`, and `Button`. Render `null` when there is no active recurring row, call `/billing/api/portal/` for billing management, and call `/billing/api/subscription/cancel/` to schedule period-end cancellation.

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

Use shadcn/ui `Table`, `ScrollArea`, and `Button`. Because the API returns a plain list without total-count metadata, use page-number state and infer whether another page exists from the configured page size (`QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE`).

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

// Keep in step with the deployment's transactions_per_page by exposing the
// same value to Vite as VITE_QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE.
const TRANSACTION_PAGE_SIZE = Number(
	import.meta.env.VITE_QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE ?? 25,
);

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

Frontend runtime wiring: load `billing/api/config/` after the user is authenticated, map the
returned `publishable_key` into your runtime config shape as `VITE_STRIPE_PUBLISHABLE_KEY` if
you want one consistent frontend config name, and feed that runtime value into `loadStripe()`
rather than storing a checked-in `.env` value.
