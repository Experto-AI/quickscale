# QuickScale Multi-Tenancy: Isolation Strategies with Real Examples & Code Changes

**Date:** December 15, 2025
**Focus:** Real-world examples of RLS vs Schema Isolation vs Database Isolation, how companies use them by tier, and required QuickScale code changes

---

## Table of Contents

1. [Real-World Examples by Company](#real-world-examples-by-company)
2. [Tenant Isolation by Customer Tier](#tenant-isolation-by-customer-tier)
3. [Technical Comparison](#technical-comparison)
4. [QuickScale Architecture Review](#quickscale-architecture-review)
5. [Code Changes Required for Each Strategy](#code-changes-required-for-each-strategy)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Real-World Examples by Company

### Supabase (Backend-as-a-Service)

**Company Overview:** Firebase alternative with PostgreSQL, Real-Time, Auth, Storage

**Pricing Tiers & Tenant Isolation:**

| Tier | Monthly Cost | Tenants/MAU | Database Tier | Isolation Strategy | Who This Is For |
|------|-------------|-------------|----------------|------------------|-----------------|
| **Free** | $0 | 50,000 MAU | Shared RDS | **RLS** (shared tables, row-level filtering) | Solo developers, learning |
| **Pro** | $25 | 100,000 MAU | Shared RDS | **RLS** (shared tables, row-level filtering) | Small teams, startups |
| **Team** | $599 | Unlimited MAU | Dedicated instance | **Schema Isolation** (dedicated schema) | Growing SMB, compliance needs |
| **Enterprise** | Custom | Unlimited | Private cloud | **Database Isolation** (dedicated database or on-premise) | Enterprise, compliance-heavy |

**Key Design Decision:** Supabase uses RLS in shared database for free/pro customers (thousands of tenants on same DB), then graduates to dedicated resources for higher tiers. User isolation via `auth.uid()` and tenant_id in JWT.

**Reference:** [Supabase Multi-Tenancy Guide](https://www.restack.io/docs/supabase-knowledge-supabase-multi-tenant-guide)

---

### Slack (Collaboration Platform)

**Company Overview:** Workspace-based communication and collaboration

**Tenant Isolation Strategy: RLS + Sharding in Single Database**

- **Architecture:** Single database for all workspaces, but with heavy sharding by workspace_id
- **Isolation:** Row-Level Security policies enforce workspace_id filtering
- **Why RLS:** Cost efficient for massive scale (millions of workspaces)
- **Tenant Type:** Workspaces (can have 1-10,000s of users per workspace)
- **Scaling:** Uses database sharding to prevent large workspaces from impacting others

**Key Design Decision:** All workspaces in shared database with RLS, but with sophisticated sharding and caching to handle noisy-neighbor problem.

**Reference:** [Slack's Multi-Tenancy Architecture - DEV Community](https://dev.to/devcorner/deep-dive-slacks-multi-tenancy-architecture-m38)

---

### Auth0 (Identity-as-a-Service)

**Company Overview:** Authentication and authorization platform

**Tenant Model: Logical Isolation (Auth0 "Tenants")**

- **Architecture:** Shared database, logical separation via tenant_id
- **Isolation:** Strict application-layer enforcement (database-level access control)
- **Who:** Each customer gets their own "tenant" namespace
- **Use Case:** Multiple organizations/applications per customer
- **Scaling:** Each tenant is logically isolated, not physically separate

**Key Design Decision:** Logical tenants with strict enforcement, not physical database/schema separation. Used for scaling to millions of authentication transactions.

**Reference:** [Auth0 Multiple Organization Architecture](https://auth0.com/docs/get-started/architecture-scenarios/multiple-organization-architecture)

---

### AWS RDS Best Practices (By AWS Recommendation)

**AWS Provides Three Models:**

| Model | Architecture | Best For | Cost | Isolation | Complexity |
|-------|--------------|----------|------|-----------|-----------|
| **Pool Model** | Shared DB, shared tables, RLS | Cost-efficient small customers | ⭐ Lowest | Row-level | Low |
| **Bridge Model** | Shared DB, separate schemas | Growing customers, some customization | ⭐⭐ Medium | Schema-level | Medium |
| **Silo Model** | Separate database per tenant | Enterprise, strict compliance | ⭐⭐⭐ High | Database-level | High |

**AWS Recommendation:** Start with Pool (RLS), graduate to Bridge (schema), then Silo (database) as customers grow and need more isolation/SLA.

**Reference:** [AWS Multi-Tenant SaaS Storage Strategies](https://aws.amazon.com/whitepapers/multi-tenant-saas-storage-strategies/)

---

### Popular SaaS Examples

**Vercel (Frontend Deployment)**
- **Teams/Organizations:** Schema isolation or separate databases
- **Free/Hobby Projects:** Shared infrastructure with RLS-like filtering
- **Enterprise:** Separate VPC and dedicated resources

**Stripe (Payment Processing)**
- **Customers:** Separate account namespaces in shared database
- **Isolation:** RLS + extensive application-layer access control
- **Scaling:** Massive scale (millions of merchants) in single database

**Shopify (E-commerce Platform)**
- **Stores:** Separate database per store (Silo model)
- **Why:** Each store can be moved to different regions, scaled independently
- **Trade-off:** High operational overhead but maximum isolation

**Twilio (Communications API)**
- **Accounts:** Shared database with RLS-like application-layer isolation
- **Sub-accounts:** Additional logical isolation layer
- **Scaling:** Millions of accounts in shared infrastructure

**Notion (Workspace/Database)**
- **Workspaces:** Separate database per workspace (Silo model)
- **Why:** Strong isolation for privacy-conscious users
- **Feature:** Users can move workspaces between regions

---

## Tenant Isolation by Customer Tier

### Typical Tiered Approach for SMB SaaS

```
┌─────────────────────────────────────────────────────────────┐
│ TYPICAL SAAS TIERING PATTERN (Based on Real Examples)      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ FREE TIER ($0/month)                                        │
│ ├─ Thousands-of-millions of tenants possible               │
│ ├─ Isolation: RLS (Row-Level Security)                     │
│ ├─ Database: Shared (multi-tenant RDS)                     │
│ ├─ SLA: Best-effort only                                   │
│ ├─ Guarantee: "Noisy neighbors" possible                   │
│ └─ Who: Individuals, hobby projects, learning             │
│                                                              │
│ STARTER ($19-29/month)                                      │
│ ├─ Hundreds-of-thousands of tenants possible              │
│ ├─ Isolation: RLS (Row-Level Security)                     │
│ ├─ Database: Shared (multi-tenant RDS)                     │
│ ├─ SLA: Best-effort (99.5% typical)                        │
│ ├─ Guarantee: Rate limiting prevents abuse                │
│ └─ Who: Solo developers, small projects, startups         │
│                                                              │
│ PRO ($79-99/month)                                          │
│ ├─ Thousands-of-tens-of-thousands possible                │
│ ├─ Isolation: PostgreSQL Schema Isolation (upgraded!)      │
│ ├─ Database: Shared (multi-tenant RDS, but 50-100/cluster)│
│ ├─ SLA: 99.5-99.9% uptime                                 │
│ ├─ Guarantee: Reduced noisy-neighbor impact               │
│ └─ Who: Small teams, growing startups                      │
│                                                              │
│ TEAM ($199-249/month)                                       │
│ ├─ Hundreds of tenants per database cluster               │
│ ├─ Isolation: Schema Isolation (dedicated schemas)         │
│ ├─ Database: Private DB cluster OR isolated schema        │
│ ├─ SLA: 99.9% uptime                                      │
│ ├─ Guarantee: No noisy-neighbor concerns                  │
│ └─ Who: SMB teams, agencies                               │
│                                                              │
│ ENTERPRISE (Custom pricing, $500+/month)                   │
│ ├─ One or few tenants per database                        │
│ ├─ Isolation: Database Isolation (separate DB)             │
│ ├─ Database: Dedicated PostgreSQL instance                │
│ ├─ SLA: 99.95%+ with SLO guarantees                       │
│ ├─ Guarantee: Guaranteed performance, compliance          │
│ └─ Who: Enterprise, healthcare, finance                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Technical Comparison

### Option 1: RLS (Row-Level Security) - Shared Database, Shared Schema

**How It Works:**
```sql
-- All tenants in same table
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name TEXT,
    email TEXT
);

-- RLS policy: Users can only see their own tenant's data
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
```

**Pros:**
- ✅ Cheapest per-tenant cost (amortized across 1000+ tenants)
- ✅ Easiest to manage (single schema, single backup)
- ✅ Best scalability for small customers
- ✅ Database-level enforcement (no app bugs can leak data)
- ✅ Simple to upgrade users (no schema migration needed)

**Cons:**
- ❌ Noisy-neighbor problem (one tenant's query affects others)
- ❌ Cannot customize schema per tenant
- ❌ Complex RLS policies can hurt performance
- ❌ Limited compliance options (all data in same database)
- ❌ Not suitable for very large tenants

**Best For:**
- Free tier (thousands+ of customers)
- Starter tier (small projects, low resource usage)
- Cost-conscious customers
- Customer type: Solo developers, small side projects

**Company Examples:**
- Supabase (Free, Pro tiers)
- Slack (all workspaces with sharding)
- Stripe (millions of merchants)

---

### Option 2: Schema Isolation - Shared Database, Separate Schemas

**How It Works:**
```sql
-- Each tenant gets own schema
CREATE SCHEMA tenant_abc123;
CREATE SCHEMA tenant_def456;

-- Same table structure, separate namespace
CREATE TABLE tenant_abc123.users (id BIGINT, name TEXT, ...);
CREATE TABLE tenant_def456.users (id BIGINT, name TEXT, ...);

-- Application sets schema search path
SET search_path = tenant_abc123;
-- All queries automatically scoped to that schema
```

**Pros:**
- ✅ Better isolation than RLS (separate tables per tenant)
- ✅ Can customize schema per tenant (indexes, columns)
- ✅ Easier per-tenant migrations
- ✅ No RLS complexity (simpler queries)
- ✅ Better performance than RLS for medium-load tenants
- ✅ Moderate cost (1000+ tenants possible, just not millions)

**Cons:**
- ❌ More expensive than RLS (more connections, more metadata)
- ❌ Metadata bloat with many schemas (affects system performance)
- ❌ Complex migrations (must run against all schemas)
- ❌ Still shared database (not compliance-friendly)
- ❌ Connection pooling complexity
- ❌ No per-tenant customization of PostgreSQL config

**Best For:**
- Pro tier ($79-99/month)
- Growing customers needing better isolation
- Customers who want per-tenant customization
- Customer type: Small teams, startups, growing projects

**Company Examples:**
- Supabase (Team tier)
- AWS recommended for "Bridge" model
- Many Django multi-tenant apps (django-tenants)

---

### Option 3: Database Isolation - Separate Database per Tenant

**How It Works:**
```sql
-- Each tenant gets completely separate database
CREATE DATABASE quickscale_tenant_abc123;
CREATE DATABASE quickscale_tenant_def456;

-- Separate connections for each
connectionA = psycopg2.connect("dbname=quickscale_tenant_abc123")
connectionB = psycopg2.connect("dbname=quickscale_tenant_def456")

-- App routes connections based on tenant_id
```

**Pros:**
- ✅ Maximum isolation (separate everything)
- ✅ Full compliance (each tenant's data never touches others)
- ✅ Can scale each tenant independently
- ✅ Can move tenants between regions easily
- ✅ Can apply different configurations per tenant
- ✅ No noisy-neighbor issues
- ✅ Can give tenants read-only database backups
- ✅ Enterprise SLAs (99.95%+) more achievable

**Cons:**
- ❌ Highest cost (separate instance per tenant, ~$50-200/month minimum per DB)
- ❌ Operational complexity (1000 databases = 1000 backups, monitoring, etc.)
- ❌ Connection pooling nightmare (thousands of connections)
- ❌ Slow onboarding (must provision new database)
- ❌ Difficult to aggregate analytics across tenants
- ❌ Only viable for high-paying customers
- ❌ Not cost-effective for free/starter tiers

**Best For:**
- Team tier ($199+/month)
- Enterprise tier ($500+/month)
- Compliance-heavy customers (healthcare, finance)
- Very large customers who need guarantees
- Customer type: Companies, agencies, enterprises

**Company Examples:**
- Shopify (each store gets database)
- Notion (each workspace gets database)
- Mattermost Cloud Enterprise (single-tenant per customer)
- Enterprise SaaS (Salesforce, HubSpot for enterprise)

---

## QuickScale Architecture Review

### Current State

**QuickScale is currently:**
- ✅ Single-instance, single-database per deployment
- ✅ User-based access control via Django groups/permissions
- ❌ No built-in multi-tenancy support
- ❌ No tenant_id concept in models
- ❌ No RLS policies
- ❌ No schema switching mechanism

**Current Database Models:**
```
User (from auth module)
├── extends AbstractUser
└── No tenant_id field

Contact (from CRM module)
├── first_name, last_name
├── company (ForeignKey)
└── No tenant_id field

Deal (from CRM module)
├── title, amount
├── contact, stage, owner
└── No tenant_id field

Post (from blog module)
├── title, content
├── author (FK to User)
└── No tenant_id field
```

**Access Control Current:**
- Django's auth.permission system
- Groups for role-based access
- No row-level filtering (all users see all data they're "allowed" to see)

---

## Code Changes Required for Each Strategy

### Strategy 1: RLS (Row-Level Security) - Shared Database

#### 1.1 Add tenant_id to Models

**File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/models.py`

**Changes to CRM Module:**
```python
# BEFORE
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quickscale_crm_contact"


# AFTER
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Contact(models.Model):
    # NEW: tenant_id for RLS
    tenant_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quickscale_crm_contact"
        # NEW: Index for RLS query performance
        indexes = [
            models.Index(fields=['tenant_id', 'created_at']),
            models.Index(fields=['tenant_id', 'email']),
        ]

# Apply to all models: Company, Deal, Tag, ContactNote, DealNote
```

**Changes to Blog Module:**
```python
# BEFORE
class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = MarkdownxField()

# AFTER
class Post(models.Model):
    tenant_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)  # Change: slug unique per tenant, not globally
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = MarkdownxField()

    class Meta:
        unique_together = [['tenant_id', 'slug']]  # NEW
        indexes = [
            models.Index(fields=['tenant_id', 'published_date']),
        ]
```

#### 1.2 Create Migration

**File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/migrations/000X_add_tenant_id.py`

```python
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('quickscale_modules_crm', '0001_initial'),
    ]

    operations = [
        # Add tenant_id to all tables
        migrations.AddField(
            model_name='contact',
            name='tenant_id',
            field=models.UUIDField(default=uuid.uuid4, db_index=True),
        ),
        migrations.AddField(
            model_name='company',
            name='tenant_id',
            field=models.UUIDField(default=uuid.uuid4, db_index=True),
        ),
        migrations.AddField(
            model_name='deal',
            name='tenant_id',
            field=models.UUIDField(default=uuid.uuid4, db_index=True),
        ),
        migrations.AddField(
            model_name='tag',
            name='tenant_id',
            field=models.UUIDField(default=uuid.uuid4, db_index=True),
        ),

        # Add indexes for performance
        migrations.AddIndex(
            model_name='contact',
            index=models.Index(fields=['tenant_id', 'created_at'], name='contact_tenant_date_idx'),
        ),
        # ... repeat for other models
    ]
```

#### 1.3 Create RLS Policies (Raw SQL Migration)

**File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/migrations/000X_rls_policies.py`

```python
from django.db import migrations, connection

def enable_rls_policies(apps, schema_editor):
    """Enable RLS policies for multi-tenant isolation"""

    with connection.cursor() as cursor:
        # Enable RLS on tables
        cursor.execute("ALTER TABLE quickscale_crm_contact ENABLE ROW LEVEL SECURITY;")
        cursor.execute("ALTER TABLE quickscale_crm_company ENABLE ROW LEVEL SECURITY;")
        cursor.execute("ALTER TABLE quickscale_crm_deal ENABLE ROW LEVEL SECURITY;")

        # Drop existing policies if they exist
        cursor.execute("DROP POLICY IF EXISTS contact_tenant_isolation ON quickscale_crm_contact;")

        # Create RLS policies
        # This policy ensures: user can only see contacts where tenant_id = their tenant_id
        cursor.execute("""
            CREATE POLICY contact_tenant_isolation ON quickscale_crm_contact
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)

        cursor.execute("""
            CREATE POLICY company_tenant_isolation ON quickscale_crm_company
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)

        cursor.execute("""
            CREATE POLICY deal_tenant_isolation ON quickscale_crm_deal
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)

def disable_rls_policies(apps, schema_editor):
    """Disable RLS policies (for rollback)"""
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE quickscale_crm_contact DISABLE ROW LEVEL SECURITY;")
        cursor.execute("ALTER TABLE quickscale_crm_company DISABLE ROW LEVEL SECURITY;")
        cursor.execute("ALTER TABLE quickscale_crm_deal DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):
    dependencies = [
        ('quickscale_modules_crm', '000X_add_tenant_id'),
    ]

    operations = [
        migrations.RunPython(enable_rls_policies, disable_rls_policies),
    ]
```

#### 1.4 Middleware to Set Tenant Context

**New File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/middleware.py`

```python
from django.db import connection

class TenantMiddleware:
    """
    Sets the tenant_id for RLS policies based on current user/organization.
    Must be added to MIDDLEWARE in settings.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get tenant_id from user profile, organization, or URL
        tenant_id = self._get_tenant_id(request)

        if tenant_id:
            # Set application parameter for RLS
            # PostgreSQL will use this in RLS policies
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    [str(tenant_id)]
                )

        response = self.get_response(request)
        return response

    def _get_tenant_id(self, request):
        """Extract tenant_id from request"""

        # Option 1: From authenticated user's profile/organization
        if request.user.is_authenticated and hasattr(request.user, 'tenant_id'):
            return request.user.tenant_id

        # Option 2: From URL parameter (for team routes)
        if 'team_id' in request.resolver_match.kwargs:
            return request.resolver_match.kwargs['team_id']

        # Option 3: From organization in path
        if 'org' in request.resolver_match.kwargs:
            # Lookup org_id -> tenant_id
            return self._get_tenant_for_org(request.resolver_match.kwargs['org'])

        return None

    def _get_tenant_for_org(self, org_slug):
        """Lookup organization and return its tenant_id"""
        # This would query your Organization/Team model
        from quickscale_modules_teams.models import Organization
        try:
            org = Organization.objects.get(slug=org_slug)
            return org.tenant_id
        except Organization.DoesNotExist:
            return None
```

**Add to settings:**
```python
# In Django settings.py (generated or project settings)
MIDDLEWARE = [
    # ... other middleware
    'quickscale_modules_crm.middleware.TenantMiddleware',
]
```

#### 1.5 Queryset Filtering Helper

**File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/managers.py`

```python
from django.db import models


class TenantAwareManager(models.Manager):
    """
    Custom manager that automatically filters by tenant_id.
    Use: Contact.tenant_objects.all() instead of Contact.objects.all()
    """

    def get_queryset(self):
        # Get current tenant from thread-local or request context
        from django.db import connection

        queryset = super().get_queryset()

        try:
            tenant_id = connection.settings_dict.get('current_tenant_id')
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
        except:
            pass

        return queryset


# In models.py
class Contact(models.Model):
    tenant_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    first_name = models.CharField(max_length=100)
    # ... other fields

    # Standard manager (for admin/scripts)
    objects = models.Manager()

    # Tenant-aware manager (for application code)
    tenant_objects = TenantAwareManager()

    class Meta:
        db_table = "quickscale_crm_contact"
```

**Usage in views:**
```python
# Old way (all contacts, needs manual filtering)
# contacts = Contact.objects.all()

# New way with RLS (safe from row perspective, but do this anyway for safety)
# contacts = Contact.tenant_objects.all()
# Or with explicit tenant context:
# contacts = Contact.objects.filter(tenant_id=tenant_id)
```

#### 1.6 Testing RLS

**File:** `quickscale_modules/{module}/tests/test_rls.py`

```python
from django.test import TestCase, TransactionTestCase
from django.db import connection
from uuid import uuid4

from quickscale_modules_crm.models import Contact, Company


class TenantIsolationTests(TransactionTestCase):
    """Test RLS tenant isolation"""

    def setUp(self):
        self.tenant_a = uuid4()
        self.tenant_b = uuid4()

        # Create data for both tenants
        self.company_a = Company.objects.create(
            tenant_id=self.tenant_a,
            name="Company A"
        )
        self.company_b = Company.objects.create(
            tenant_id=self.tenant_b,
            name="Company B"
        )

        self.contact_a = Contact.objects.create(
            tenant_id=self.tenant_a,
            first_name="John",
            last_name="Doe",
            company=self.company_a
        )
        self.contact_b = Contact.objects.create(
            tenant_id=self.tenant_b,
            first_name="Jane",
            last_name="Smith",
            company=self.company_b
        )

    def test_rls_isolation_tenant_a(self):
        """Tenant A can only see their own data via RLS"""
        with connection.cursor() as cursor:
            # Set tenant context
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                [str(self.tenant_a)]
            )

            # Query should only return tenant A's contact
            cursor.execute("SELECT id FROM quickscale_crm_contact;")
            results = cursor.fetchall()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0], self.contact_a.id)

    def test_rls_isolation_tenant_b(self):
        """Tenant B can only see their own data via RLS"""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                [str(self.tenant_b)]
            )

            cursor.execute("SELECT id FROM quickscale_crm_contact;")
            results = cursor.fetchall()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0], self.contact_b.id)

    def test_rls_prevents_cross_tenant_access(self):
        """RLS prevents direct access to other tenant's data"""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                [str(self.tenant_a)]
            )

            # Try to access tenant B's contact (should fail silently)
            cursor.execute(
                "SELECT id FROM quickscale_crm_contact WHERE id = %s;",
                [self.contact_b.id]
            )

            results = cursor.fetchall()
            self.assertEqual(len(results), 0)  # No results due to RLS
```

---

### Strategy 2: Schema Isolation - Separate Schema per Tenant

#### 2.1 Schema Creation on Tenant Signup

**New File:** `quickscale_modules/teams/src/quickscale_modules_teams/schema_manager.py`

```python
from django.db import connection
from django.core.management import call_command
import uuid


class SchemaManager:
    """Manages schema creation, migration, and cleanup for tenants"""

    @staticmethod
    def create_schema(tenant_id):
        """Create isolated schema for tenant"""
        schema_name = f"tenant_{tenant_id.hex}"

        with connection.cursor() as cursor:
            # Create schema
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")

            # Create all tables in this schema
            # Option 1: Run migrations on this schema
            call_command(
                'migrate',
                database=connection.alias,
                schema=schema_name
            )

            # Option 2: Or use raw SQL to create tables
            # cursor.execute(f"CREATE TABLE {schema_name}.users AS SELECT * FROM public.users LIMIT 0;")

        return schema_name

    @staticmethod
    def get_schema_name(tenant_id):
        """Get schema name for tenant"""
        return f"tenant_{tenant_id.hex}"

    @staticmethod
    def drop_schema(tenant_id, cascade=True):
        """Drop tenant's schema (for cleanup)"""
        schema_name = SchemaManager.get_schema_name(tenant_id)

        with connection.cursor() as cursor:
            if cascade:
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")
            else:
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name};")
```

#### 2.2 Middleware to Switch Schemas

**File:** `quickscale_modules/teams/src/quickscale_modules_teams/middleware.py`

```python
from django.db import connection
from .schema_manager import SchemaManager


class SchemaMiddleware:
    """
    Switches PostgreSQL schema based on tenant.
    All queries automatically scoped to tenant's schema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = self._get_tenant_id(request)

        if tenant_id:
            schema_name = SchemaManager.get_schema_name(tenant_id)

            # Set search_path so all unqualified queries use this schema
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path = {schema_name}, public;")

            # Store in request for reference
            request.tenant_id = tenant_id
            request.schema_name = schema_name

        response = self.get_response(request)
        return response

    def _get_tenant_id(self, request):
        """Extract tenant_id from request"""
        # Similar to RLS implementation
        if request.user.is_authenticated and hasattr(request.user, 'tenant_id'):
            return request.user.tenant_id

        if 'org' in request.resolver_match.kwargs:
            from quickscale_modules_teams.models import Organization
            try:
                org = Organization.objects.get(slug=request.resolver_match.kwargs['org'])
                return org.tenant_id
            except Organization.DoesNotExist:
                return None

        return None
```

#### 2.3 Model Changes (Simpler than RLS)

**File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/models.py`

```python
# With schema isolation, you DON'T need tenant_id in every model
# Just use the schema switching middleware

# BEFORE
class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    # ... fields

# AFTER (no change needed! Schema is handled by middleware)
class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    # ... same fields, but queries automatically scoped to schema

# Uniqueness constraints now work per-tenant automatically:
class Post(models.Model):
    slug = models.SlugField(unique=True)  # Unique per schema (per tenant)
    # ... fields
```

#### 2.4 Database Connection Routing

**File:** `quickscale_core/src/quickscale_core/db_router.py`

```python
class SchemaRouter:
    """Route all queries through schema-aware connection"""

    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if both in same schema"""
        # Both should be in same schema via middleware
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Allow migrations on default database"""
        return db == 'default'
```

---

### Strategy 3: Database Isolation - Separate Database per Tenant

#### 3.1 Tenant Database Registry

**New File:** `quickscale_modules/teams/src/quickscale_modules_teams/db_registry.py`

```python
from django.conf import settings
from django.db import connections, connection


class TenantDatabaseRegistry:
    """
    Manages database connections for each tenant.
    Maintains mapping of tenant_id -> database credentials.
    """

    # In-memory cache (in production, use Redis or database)
    _cache = {}

    @classmethod
    def get_db_config(cls, tenant_id):
        """Get database config for tenant"""

        # Check cache
        if tenant_id in cls._cache:
            return cls._cache[tenant_id]

        # Query database to find tenant's connection details
        from quickscale_modules_teams.models import TenantDatabase

        try:
            tenant_db = TenantDatabase.objects.get(tenant_id=tenant_id)
            config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': tenant_db.database_name,
                'USER': tenant_db.db_user,
                'PASSWORD': tenant_db.db_password,
                'HOST': tenant_db.db_host,
                'PORT': tenant_db.db_port,
            }

            cls._cache[tenant_id] = config
            return config

        except TenantDatabase.DoesNotExist:
            raise Exception(f"No database configured for tenant {tenant_id}")

    @classmethod
    def register_tenant_database(cls, tenant_id, db_config):
        """Register new tenant database (called on signup)"""

        from quickscale_modules_teams.models import TenantDatabase

        TenantDatabase.objects.create(
            tenant_id=tenant_id,
            database_name=db_config['NAME'],
            db_user=db_config['USER'],
            db_password=db_config['PASSWORD'],
            db_host=db_config['HOST'],
            db_port=db_config['PORT'],
        )

        # Add to Django's DATABASES setting
        settings.DATABASES[f'tenant_{tenant_id.hex}'] = db_config

        # Clear cache
        if tenant_id in cls._cache:
            del cls._cache[tenant_id]
```

#### 3.2 Database Provisioning Service

**New File:** `quickscale_modules/teams/src/quickscale_modules_teams/database_provisioner.py`

```python
import uuid
import psycopg2
from django.conf import settings


class DatabaseProvisioner:
    """Provisions new PostgreSQL databases for tenants"""

    @classmethod
    def provision_tenant_database(cls, tenant_id, parent_connection=None):
        """
        Create new database for tenant.
        Usually called when organization/team is created.
        """

        if parent_connection is None:
            parent_connection = settings.ADMIN_DATABASE_URL

        # Connect to main PostgreSQL instance as admin
        conn = psycopg2.connect(parent_connection)
        conn.autocommit = True

        cursor = conn.cursor()

        try:
            # Generate database name
            db_name = f"quickscale_tenant_{tenant_id.hex[:16]}"

            # Create database
            cursor.execute(f"CREATE DATABASE {db_name};")

            # Create role for this tenant (for security)
            db_user = f"tenant_{tenant_id.hex[:16]}"
            db_password = str(uuid.uuid4())

            cursor.execute(
                f"CREATE USER {db_user} WITH ENCRYPTED PASSWORD %s;",
                (db_password,)
            )

            # Grant permissions
            cursor.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {db_user};")
            cursor.execute(f"ALTER DATABASE {db_name} OWNER TO {db_user};")

            # Run migrations on new database
            new_db_config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': db_name,
                'USER': db_user,
                'PASSWORD': db_password,
                'HOST': settings.DATABASES['default']['HOST'],
                'PORT': settings.DATABASES['default']['PORT'],
            }

            # Register in registry
            from .db_registry import TenantDatabaseRegistry
            TenantDatabaseRegistry.register_tenant_database(tenant_id, new_db_config)

            # Run migrations
            from django.core.management import call_command
            call_command('migrate', database=f'tenant_{tenant_id.hex}')

            return new_db_config

        finally:
            cursor.close()
            conn.close()
```

#### 3.3 Middleware to Route Connections

**File:** `quickscale_modules/teams/src/quickscale_modules_teams/db_middleware.py`

```python
from django.db import connections
from .db_registry import TenantDatabaseRegistry


class DatabaseRoutingMiddleware:
    """
    Routes database connections to tenant-specific databases.
    Each request connects to its tenant's database.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = self._get_tenant_id(request)

        if tenant_id:
            # Get tenant's database config
            db_config = TenantDatabaseRegistry.get_db_config(tenant_id)

            # Create connection alias
            db_alias = f'tenant_{tenant_id.hex}'

            if db_alias not in connections:
                from django.db import DEFAULT_DB_ALIAS
                connections.create_connection(db_alias, db_config)

            # Set as default for this request
            request.tenant_db_alias = db_alias

        response = self.get_response(request)
        return response

    def _get_tenant_id(self, request):
        """Extract tenant_id from request"""
        if request.user.is_authenticated and hasattr(request.user, 'tenant_id'):
            return request.user.tenant_id
        return None
```

#### 3.4 Model Manager with DB Routing

**File:** `quickscale_modules/{module}/src/quickscale_modules_{module}/managers.py`

```python
from django.db import models
from django.db import DEFAULT_DB_ALIAS, connections
from django.apps import apps


class TenantDatabaseManager(models.Manager):
    """
    Routes queries to tenant's database.
    Must store db_alias in request context or thread-local.
    """

    def get_queryset(self):
        qs = super().get_queryset()

        # Get current tenant's database
        db_alias = self._get_db_alias()
        if db_alias:
            qs = qs.using(db_alias)

        return qs

    def _get_db_alias(self):
        """Get current request's tenant database alias"""
        # Option 1: From thread-local context
        from .context import get_current_tenant_db
        return get_current_tenant_db()

    def create(self, **kwargs):
        """Ensure creation uses tenant's database"""
        db_alias = self._get_db_alias()
        if db_alias:
            return super().create_on_db(db_alias, **kwargs)
        return super().create(**kwargs)


# In models.py
class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    # ... fields

    objects = TenantDatabaseManager()

    class Meta:
        db_table = "quickscale_crm_contact"
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Add tenant_id concept to QuickScale:**

1. [ ] Add tenant_id (UUID) to all models (required for all strategies)
2. [ ] Create Team/Organization model (owner of tenant)
3. [ ] Create User→Team relationship model
4. [ ] Add module configuration option for tenancy strategy

**Code files to modify:**
- `quickscale_modules/*/models.py` - Add tenant_id
- `quickscale_modules/teams/models.py` - Create Organization, UserTeam models
- `quickscale_core/manifest/schema.py` - Add tenancy_strategy option

### Phase 2: Choose & Implement Strategy (Weeks 3-8)

**For RLS (Recommended for MVP):**
1. [ ] Create RLS migration with policies
2. [ ] Create TenantMiddleware to set app.current_tenant_id
3. [ ] Update views to pass tenant_id to template context
4. [ ] Add tests for RLS policies
5. [ ] Documentation for RLS usage

**For Schema Isolation (Plan B):**
1. [ ] Create SchemaManager for schema operations
2. [ ] Create SchemaMiddleware to switch schemas
3. [ ] Create schema setup on organization creation
4. [ ] Add tests for schema isolation
5. [ ] Documentation for schema isolation

**For Database Isolation (Enterprise):**
1. [ ] Create TenantDatabaseRegistry
2. [ ] Create DatabaseProvisioner
3. [ ] Create DatabaseRoutingMiddleware
4. [ ] Create database provisioning service (manual or automated)
5. [ ] Add tests for database routing

### Phase 3: Admin & Management (Weeks 9-10)

1. [ ] Admin UI to view tenants/organizations
2. [ ] Admin commands to migrate between strategies
3. [ ] Tenant analytics (storage, users, activity)
4. [ ] Billing integration per tenant
5. [ ] Monitoring & alerting per tenant

### Phase 4: Testing & Documentation (Week 11-12)

1. [ ] Integration tests for each strategy
2. [ ] Performance benchmarks
3. [ ] Documentation for each strategy
4. [ ] Migration guides (single-tenant → multi-tenant)
5. [ ] Troubleshooting guide

---

## Comparison Summary

### Quick Decision Matrix

| Requirement | RLS | Schema | Database |
|-------------|-----|--------|----------|
| **Cost per 1000 tenants** | $5-20/month | $20-50/month | $500-2000/month |
| **Maximum tenants** | 1M+ | 10K-100K | 100-1000 |
| **Noisy neighbor risk** | High | Low | None |
| **Setup complexity** | Low | Medium | High |
| **Customization per tenant** | None | High | Very High |
| **Compliance certification** | Possible | Possible | Yes |
| **Ideal for Free tier** | ✅ | ❌ | ❌ |
| **Ideal for Pro tier** | ✅ | ✅ | ❌ |
| **Ideal for Enterprise** | ❌ | ❌ | ✅ |

---

## Sources

### Multi-Tenancy Architecture
- [AWS Multi-Tenant SaaS Storage Strategies](https://aws.amazon.com/whitepapers/multi-tenant-saas-storage-strategies/)
- [AWS: Choose the Right PostgreSQL Pattern for SaaS](https://aws.amazon.com/blogs/database/choose-the-right-postgresql-data-access-pattern-for-your-saas-application/)
- [Multi-Tenant Data Isolation with PostgreSQL RLS - AWS Database Blog](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/)

### Supabase
- [Supabase Multi-Tenancy Guide](https://www.restack.io/docs/supabase-knowledge/supabase-multi-tenant-guide)
- [Supabase Row Level Security - Official Docs](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase Pricing - Multi-Tenant Breakdown](https://flexprice.io/blog/supabase-pricing-breakdown)

### Real-World Examples
- [Slack's Multi-Tenancy Architecture - DEV Community](https://dev.to/devcorner/deep-dive-slacks-multi-tenancy-architecture-m38)
- [Auth0: Multiple Organization Architecture](https://auth0.com/docs/get-started/architecture-scenarios/multiple-organization-architecture)

### Django Multi-Tenancy
- [Building a Multi-Tenant App with Django - TestDriven.io](https://testdriven.io/blog/django-multi-tenant/)
- [django-tenants Documentation](https://django-tenants.readthedocs.io/)
- [django-tenant-schemas Documentation](https://django-tenant-schemas.readthedocs.io/)

### PostgreSQL RLS
- [PostgreSQL Row Level Security - Official Docs](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Multi-Tenant Applications with RLS on Supabase - AntStack](https://www.antstack.com/blog/multi-tenant-applications-with-rls-on-supabase-postgress/)
- [Shipping Multi-Tenant SaaS Using Postgres RLS - The Nile](https://www.thenile.dev/blog/multi-tenant-rls)

---

**Document Complete**
Last updated: December 15, 2025
