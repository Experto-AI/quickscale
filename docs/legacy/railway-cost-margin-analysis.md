# Railway Infrastructure Cost & Margin Analysis for QuickScale

**Date:** December 15, 2025
**Platform:** Railway
**Focus:** Single-tenant vs multi-tenant cost structures with margin implications

---

## Railway Pricing Rates (Current - December 2025)

**Compute Resources:**
- vCPU: **$20/month** per full CPU (or $0.000463/minute)
- Memory: **$10/month** per GB (or $0.000231/minute)
- Storage: **$0.15/month** per GB
- Network Egress: **$0.05/GB**

**Pricing Tiers:**
- Hobby: $5/month base + usage
- Pro: $20/month base + usage
- Enterprise: Custom

**References:** [Railway Pricing](https://railway.com/pricing), [Railway Pricing Docs](https://docs.railway.com/reference/pricing/plans)

---

## Cost Model 1: Single-Tenant per Customer

Each customer gets their own dedicated app instance + PostgreSQL database.

### Scenario A: Small Instance (0.5 CPU / 1 GB RAM)

**Monthly Infrastructure Costs per Customer:**

```
Frontend App Instance:
├─ vCPU:        0.5 × $20 = $10.00
├─ Memory:      1.0 × $10 = $10.00
├─ Storage:     10 GB × $0.15 = $1.50
├─ Egress:      20 GB/month × $0.05 = $1.00
└─ Subtotal:               $22.50

PostgreSQL Database:
├─ vCPU:        0.5 × $20 = $10.00
├─ Memory:      1.0 × $10 = $10.00
├─ Storage:     10 GB × $0.15 = $1.50
└─ Subtotal:               $21.50

Total Infrastructure Cost: $44.00/month per customer
```

**Margin Analysis at Different Price Points:**

| Price Point | Monthly Revenue | COGS | Gross Margin | Gross Margin % |
|-------------|-----------------|------|--------------|----------------|
| $19/month | $19.00 | $44.00 | -$25.00 | **-132%** ❌ |
| $29/month | $29.00 | $44.00 | -$15.00 | **-52%** ❌ |
| $49/month | $49.00 | $44.00 | $5.00 | **10%** ❌ |
| $79/month | $79.00 | $44.00 | $35.00 | **44%** ✅ |
| $99/month | $99.00 | $44.00 | $55.00 | **56%** ✅ |

**Verdict:** Single-tenant at 0.5 CPU/1GB requires $79+/month to be viable.

---

### Scenario B: Medium Instance (1 CPU / 2 GB RAM)

**Monthly Infrastructure Costs per Customer:**

```
Frontend App Instance:
├─ vCPU:        1.0 × $20 = $20.00
├─ Memory:      2.0 × $10 = $20.00
├─ Storage:     10 GB × $0.15 = $1.50
├─ Egress:      30 GB/month × $0.05 = $1.50
└─ Subtotal:               $43.00

PostgreSQL Database:
├─ vCPU:        0.5 × $20 = $10.00
├─ Memory:      1.0 × $10 = $10.00
├─ Storage:     20 GB × $0.15 = $3.00
└─ Subtotal:               $23.00

Total Infrastructure Cost: $66.00/month per customer
```

**Margin Analysis:**

| Price Point | Monthly Revenue | COGS | Gross Margin | Gross Margin % |
|-------------|-----------------|------|--------------|----------------|
| $19/month | $19.00 | $66.00 | -$47.00 | **-247%** ❌ |
| $29/month | $29.00 | $66.00 | -$37.00 | **-128%** ❌ |
| $49/month | $49.00 | $66.00 | -$17.00 | **-35%** ❌ |
| $79/month | $79.00 | $66.00 | $13.00 | **16%** ❌ |
| $99/month | $99.00 | $66.00 | $33.00 | **33%** ✅ |
| $129/month | $129.00 | $66.00 | $63.00 | **49%** ✅ |

**Verdict:** Single-tenant at 1 CPU/2GB requires $99+/month. Much worse economics.

---

### Single-Tenant Summary

**Problem:**
- Infrastructure costs are too high relative to SMB pricing tiers
- Would need to charge $79-129/month just to break even
- Uncompetitive with multi-tenant platforms (Vercel, Netlify, Railway's own pricing)
- Not viable for Free/Starter tiers

**Best Case:** If customer uses instance 100% of the time
**Realistic Case:** Many instances idle during off-hours (still charged same rate on Railway)

---

## Cost Model 2: Multi-Tenant Shared Infrastructure

Shared infrastructure serving multiple customers with graduated scaling.

### Scenario C: Multi-Tenant with 2 App Instances + Redis + Shared PostgreSQL

**Infrastructure Setup:**

```
Frontend Load Balancer (Node.js/Next.js):
├─ Base Instance:    0.5 CPU / 1 GB RAM
├─ Replica 1:        0.5 CPU / 1 GB RAM (for HA)
└─ Replica 2:        0.5 CPU / 1 GB RAM (for peak load)

Backend API (Python/Django):
├─ Base Instance:    1.0 CPU / 2 GB RAM
├─ Replica 1:        1.0 CPU / 2 GB RAM (autoscale)
└─ Replica 2:        1.0 CPU / 2 GB RAM (autoscale)

Redis Cache:
├─ Instance:         0.5 CPU / 1 GB RAM
└─ (optional standby for HA)

PostgreSQL Database (Shared):
├─ Primary:          1.0 CPU / 2 GB RAM
├─ Replica (HA):     1.0 CPU / 2 GB RAM
├─ Storage:          100 GB (shared across all tenants)
└─ Estimated: 500 GB with backups
```

**Monthly Cost Calculation:**

```
Frontend Instances (3 replicas × pay-per-minute usage):
├─ Average: 2 running (1.5 during peak, 1 during off-peak)
├─ Cost: 1.5 × (0.5 CPU × $20 + 1.0 GB × $10) × 1 month
├─ Cost: 1.5 × $15 × 1 = $22.50
└─ Subtotal: $22.50

Backend Instances (3 instances, autoscaling):
├─ Average: 2.5 running
├─ Cost: 2.5 × (1.0 CPU × $20 + 2.0 GB × $10)
├─ Cost: 2.5 × $40 = $100.00
└─ Subtotal: $100.00

Redis Cache:
├─ Cost: 0.5 CPU × $20 + 1 GB × $10 = $20.00
└─ Subtotal: $20.00

PostgreSQL Database (Primary + Replica):
├─ Primary:   1.0 × $20 + 2.0 × $10 = $40.00
├─ Replica:   1.0 × $20 + 2.0 × $10 = $40.00
├─ Storage:   500 GB × $0.15 = $75.00
└─ Subtotal: $155.00

Network Egress (shared across all tenants):
├─ Estimate: 5 GB/tenant × N tenants
├─ At 100 tenants: 500 GB × $0.05 = $25.00
├─ Per-tenant allocation: $25 / 100 = $0.25
└─ Subtotal: $0.25 per tenant

TOTAL INFRASTRUCTURE COST: $297.75/month (fixed)
```

**Cost Per Tenant (Amortized):**

| # Tenants | Fixed Cost | Cost/Tenant | Viability |
|-----------|-----------|-------------|-----------|
| 10 | $297.75 | $29.78/tenant | Breakeven at $29.78 |
| 25 | $297.75 | $11.91/tenant | Profitable at $19+ ✅ |
| 50 | $297.75 | $5.96/tenant | Very profitable at $19+ ✅✅ |
| 100 | $297.75 | $2.98/tenant | Extremely profitable ✅✅✅ |
| 250 | $297.75 | $1.19/tenant | Can add more replicas |
| 500 | $297.75 | $0.60/tenant | Add DB replicas/cluster |
| 1000 | $297.75 | $0.30/tenant | Scaling mode |

**As you grow, you may need:**
- More replicas (add ~$40/month per backend replica)
- Redis clustering (add ~$20/month)
- DB read replicas (add ~$40/month each)

---

### Scenario D: Multi-Tenant Scaling Profile

**Month 1-3 (Growth Phase):**
```
Tenants: 10-25 customers
Infrastructure:
├─ Fixed: $297.75/month
├─ Cost/tenant: $11.91-$29.78
├─ Revenue @ $19/month: $190-475
├─ Status: PROFITABLE even at 10 customers! ✅
```

**Month 4-6 (Expansion):**
```
Tenants: 50-100 customers
Infrastructure:
├─ Fixed: $297.75 + some additional replicas
├─ Additional replicas: ~$80/month (2 extra backend replicas)
├─ Total: ~$378/month
├─ Cost/tenant @ 75 customers: $5.04
├─ Revenue @ $19/month: $1,425
├─ Margin: 99.6% gross margin ✅✅✅
```

**Month 12 (Scale):**
```
Tenants: 250+ customers
Infrastructure:
├─ Fixed infrastructure: ~$400-500/month
├─ With multiple read replicas: ~$600/month
├─ Cost/tenant: $2.40
├─ Revenue @ $19/month × 250: $4,750
├─ Gross margin: 87%+ ✅✅✅
```

---

## Detailed Margin Comparison

### Option A: Single-Tenant Small (0.5 CPU / 1GB)

```
Customer Tier | Price | COGS | Margin | Margin % | Feasible?
──────────────────────────────────────────────────────────────
Free          | $0   | $44  | -$44   | N/A      | ❌
Starter       | $19  | $44  | -$25   | -132%    | ❌
Pro           | $79  | $44  | $35    | 44%      | ✅ (barely)
Team          | $199 | $44  | $155   | 78%      | ✅✅
Enterprise    | $500 | $44  | $456   | 91%      | ✅✅✅
```

**Problem:** Can't offer Free or Starter tiers. Minimum $79/month.

---

### Option B: Single-Tenant Medium (1 CPU / 2GB)

```
Customer Tier | Price | COGS | Margin | Margin % | Feasible?
──────────────────────────────────────────────────────────────
Free          | $0   | $66  | -$66   | N/A      | ❌
Starter       | $19  | $66  | -$47   | -247%    | ❌
Pro           | $79  | $66  | $13    | 16%      | ❌ (bad margin)
Team          | $199 | $66  | $133   | 67%      | ✅
Enterprise    | $500 | $66  | $434   | 87%      | ✅✅✅
```

**Problem:** Pro tier barely breaks even. No Free/Starter. Bad margins.

---

### Option C: Multi-Tenant (Shared Infrastructure)

```
Tier      | Price   | # Tenants | Cost/Tenant | Margin | Margin % | Feasible?
─────────────────────────────────────────────────────────────────────────────
Free      | $0      | 100-200   | $1.49-3.00  | -$1.49-0 | N/A | ⚠️ (loss leader)
Starter   | $19/mo  | 100       | $2.98       | $16.02 | 84%  | ✅✅✅
Pro       | $79/mo  | 50        | $5.96       | $73.04 | 92%  | ✅✅✅
Team      | $199/mo | 25        | $11.91      | $187   | 94%  | ✅✅✅
Enterprise| Custom  | 10        | $29.78      | Huge   | 97%+ | ✅✅✅✅
```

**Advantage:** Can profitably offer Free and Starter tiers with volume.

---

## Break-Even Analysis

### Single-Tenant Scenarios

**Small Instance (0.5 CPU / 1GB) @ $44/month COGS:**
```
Customer pays $79/month
├─ Revenue: $79
├─ COGS: $44
├─ Gross Profit: $35
├─ Gross Margin: 44%
├─ But operating costs: ~$20-30/customer (support, payment processor, etc.)
└─ Net Margin: 15-25% (barely viable)
```

**Medium Instance (1 CPU / 2GB) @ $66/month COGS:**
```
Customer pays $99/month
├─ Revenue: $99
├─ COGS: $66
├─ Gross Profit: $33
├─ Gross Margin: 33% (LOW)
├─ Operating costs: ~$20-30/customer
└─ Net Margin: 3-13% (very thin)
```

**Problem:** Insufficient margin to cover operations, support, marketing CAC.

---

### Multi-Tenant Scenario

**Shared Infrastructure @ $3/month per tenant (100 tenants):**
```
Customer pays $19/month
├─ Revenue: $19
├─ COGS: $3
├─ Gross Profit: $16
├─ Gross Margin: 84% (EXCELLENT)
├─ Operating costs: ~$8-10/customer (amortized)
└─ Net Margin: 20-25% (healthy, sustainable)
```

**As scale grows to 500 tenants:**
```
Per-tenant COGS drops to $0.60
├─ Revenue @ $19: $19
├─ COGS: $0.60
├─ Gross Profit: $18.40
├─ Gross Margin: 97% (EXCEPTIONAL)
├─ Operating costs: ~$3-5/customer (per-tenant support)
└─ Net Margin: 50-60% (excellent SaaS metrics)
```

---

## Scaling Implications

### Single-Tenant: Linear Cost Growth

```
10 customers × $44 COGS = $440/month infra
100 customers × $44 COGS = $4,400/month infra
1000 customers × $44 COGS = $44,000/month infra

Growing infrastructure costs never improve!
Every new customer adds full $44 to costs.
```

### Multi-Tenant: Sublinear Cost Growth

```
10 customers: $300 fixed infrastructure → $30/customer
100 customers: $300 fixed + $80 for extra replicas → $3.80/customer
1000 customers: $300 fixed + $200 for scaling → $0.50/customer

Economies of scale! Each new customer costs less than the previous one.
```

---

## Revenue Impact at Scale

### Single-Tenant Revenue

**Assumption:** 100 customers at $79-99/month (Pro tier minimum)

```
100 customers × $79/month = $7,900 MRR
├─ Infrastructure COGS: 100 × $44 = $4,400
├─ Gross Margin: $3,500 (44%)
├─ Operating costs (support, marketing, payments): ~$2,500
└─ Net Margin: $1,000 (13%)

Problem:
- Can't compete with multi-tenant offerings
- Can't offer Free tier (100% loss per customer)
- Can't offer Starter tier (negative margin)
- Losing to Vercel/Netlify/Railway free tiers
```

---

### Multi-Tenant Revenue

**Assumption:** 250 customers at tiered pricing

```
Tier Distribution:
├─ Free tier: 100 customers × $0 = $0
├─ Starter: 100 customers × $19 = $1,900
├─ Pro: 40 customers × $79 = $3,160
├─ Team: 10 customers × $199 = $1,990
└─ Total Revenue: $7,050 MRR

Infrastructure COGS:
├─ Fixed platform: $400/month
├─ DB replicas: $100/month
├─ Extra replicas: $100/month
├─ Total COGS: $600/month

Margin Analysis:
├─ Cost/tenant: $600 / 250 = $2.40
├─ Revenue: $7,050
├─ COGS: $600
├─ Gross Margin: $6,450 (91%)
├─ Operating costs: ~$1,500 (support, marketing amortized)
└─ Net Margin: $4,950 (70%)

Advantage:
- Much higher absolute profit ($4,950 vs $1,000)
- Better margins (70% vs 13%)
- Can compete with free offerings
- Sustainable growth
```

---

## Recommendation: Multi-Tenant Pricing Strategy

Based on this analysis, here's the optimal pricing structure for Railway:

### Tier Structure

```
┌─────────────────────────────────────────────────────────┐
│ FREE TIER                                               │
│ ├─ 1 app hosted                                         │
│ ├─ 0.5 GB memory limit                                  │
│ ├─ Multi-tenant shared infrastructure                   │
│ ├─ Infrastructure Cost: ~$1.50/customer (at scale)      │
│ ├─ Revenue: $0                                          │
│ └─ Role: Acquisition funnel, community building         │
│                                                          │
│ STARTER - $19/month                                     │
│ ├─ 3-5 apps hosted                                      │
│ ├─ 2 GB memory limit per app                            │
│ ├─ Multi-tenant shared infrastructure                   │
│ ├─ Infrastructure Cost: ~$2.40/customer                 │
│ ├─ Revenue: $19                                         │
│ ├─ Gross Margin: 87%                                    │
│ └─ Target: Solo developers, indie hackers              │
│                                                          │
│ PRO - $79/month                                         │
│ ├─ 10-20 apps hosted                                    │
│ ├─ 5 GB memory limit per app                            │
│ ├─ Upgraded to schema isolation (or own DB cluster)     │
│ ├─ Infrastructure Cost: ~$5-8/customer                  │
│ ├─ Revenue: $79                                         │
│ ├─ Gross Margin: 90%                                    │
│ └─ Target: Small teams, startups                        │
│                                                          │
│ TEAM - $199/month                                       │
│ ├─ Unlimited apps                                       │
│ ├─ Dedicated DB cluster with replicas                   │
│ ├─ Schema isolation tier                                │
│ ├─ Infrastructure Cost: ~$12-15/customer                │
│ ├─ Revenue: $199                                        │
│ ├─ Gross Margin: 93%                                    │
│ └─ Target: SMB teams, agencies                          │
│                                                          │
│ ENTERPRISE - Custom                                     │
│ ├─ Single-tenant option                                 │
│ ├─ Dedicated resources                                  │
│ ├─ Custom SLAs                                          │
│ ├─ Infrastructure Cost: Variable (10-50/month)          │
│ ├─ Minimum: $500-1000/month                             │
│ └─ Target: Compliance-heavy, large companies           │
└─────────────────────────────────────────────────────────┘
```

---

## Key Numbers Summary Table

| Metric | Single-Tenant Small | Single-Tenant Medium | Multi-Tenant |
|--------|--------------------|--------------------|--------------|
| **Infrastructure Cost per Customer** | $44/month | $66/month | $3/month (at 100 tenants) |
| **Minimum Viable Price** | $79/month | $99/month | $19/month |
| **Gross Margin @ Min Price** | 44% | 33% | 84% |
| **Can Support Free Tier?** | ❌ | ❌ | ✅ (at scale) |
| **Can Support Starter @ $19?** | ❌ | ❌ | ✅ |
| **Max Customers (Sustainable)** | 50-100 | 50-100 | 500+ |
| **MRR @ 100 Customers** | $7,900 | $9,900 | $7,000+ |
| **Net Margin @ 100 Customers** | 13% | 8% | 70% |
| **Operational Simplicity** | Complex (100 DBs) | Complex (100 DBs) | Simple (1-2 shared) |
| **Scalability** | Poor | Poor | Excellent |

---

## Implementation Recommendation

**Phase 1: Start Multi-Tenant (Weeks 1-8)**
1. Build shared platform with 2-3 app instances + Redis + shared DB
2. Launch Free tier (acquisition at scale)
3. Launch Starter @ $19/month
4. Infrastructure cost: ~$300/month initially
5. At 25 customers: Profitable on Starter tier alone

**Phase 2: Add Schema Isolation (Weeks 9-16)**
1. Upgrade Pro tier customers to schema isolation
2. Add dedicated DB cluster for Pro tier
3. Infrastructure cost: ~$400/month
4. At 50 Pro customers: 90%+ gross margin

**Phase 3: Enterprise Options (Weeks 17+)**
1. Offer single-tenant option for Enterprise
2. Offer higher-tier PRO with single-tenant @ $249+/month
3. Target high-value customers
4. Extremely profitable at enterprise scale

**Do NOT Start Single-Tenant (Unless Enterprise-Only)**
- Cost structure is fundamentally broken for SMB
- Uncompetitive with free tiers
- Can't achieve sustainable margins
- Operational nightmare (100+ databases)
- Only viable at $79+ price points

---

## Sources

- [Railway Pricing](https://railway.com/pricing)
- [Railway Pricing Docs](https://docs.railway.com/reference/pricing/plans)
- [Railway Pricing FAQs](https://docs.railway.com/reference/pricing/faqs)

---

**Document Complete**
Last updated: December 15, 2025
