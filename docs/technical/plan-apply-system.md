# QuickScale Plan/Apply System

**Technical Specification for Terraform-style Project Configuration**

**Version**: 1.0
**Status**: Planned (v0.68.0-v0.71.0)
**Last Updated**: 2025-11-28

---

## Overview

QuickScale implements a Terraform-style plan/apply workflow for project configuration. Users declare desired state in YAML, and QuickScale applies changes incrementally.

**Core Principle**: Declarative YAML (WHAT, not HOW). The YAML describes what you want; the execution engine knows the correct order.

---

## Commands

| Command | Purpose |
|---------|---------|
| `quickscale plan <name>` | Interactive wizard → creates `quickscale.yml` |
| `quickscale plan --add` | Add modules to existing project |
| `quickscale plan --edit` | Reconfigure existing modules |
| `quickscale apply [config]` | Execute configuration (default: `quickscale.yml`) |
| `quickscale status` | Show current vs desired state |
| `quickscale remove <module>` | Remove embedded module |

**Note**: Interactive mode is default. No `--no-interactive` flag exists.

---

## Complete Command Structure

After v0.71.0, QuickScale uses a clean command structure:

```
quickscale
├── Project Configuration (plan/apply)
│   ├── plan <name>           Create new project config
│   ├── plan --add            Add modules to existing project
│   ├── plan --edit           Reconfigure mutable options
│   ├── apply                 Execute configuration
│   ├── status                Show current vs desired state
│   └── remove <module>       Remove embedded module
│
├── Module Code Sync (git subtree)
│   ├── update                Pull latest module code from upstream
│   └── push                  Push improvements back to QuickScale
│
├── Development (Docker)
│   ├── up                    Start services
│   ├── down                  Stop services
│   ├── logs                  View logs
│   ├── shell                 Container shell
│   ├── manage <cmd>          Django management commands
│   └── ps                    Service status
│
└── Deployment
    └── deploy railway        Deploy to Railway
```

**Removed Commands** (replaced by plan/apply):
- ~~`quickscale init`~~ → Use `quickscale plan <name>` + `quickscale apply`
- ~~`quickscale embed`~~ → Use `quickscale plan --add` + `quickscale apply`

**Two Orthogonal Concerns**:
| Concern | Commands | Purpose |
|---------|----------|---------|
| **Configuration** | `plan`, `apply`, `status`, `remove` | What modules to install and how to configure them |
| **Code Updates** | `update`, `push` | Sync module code with QuickScale upstream |

---

## File Structure

```
myapp/
├── quickscale.yml              # Desired state (user edits)
├── .quickscale/
│   └── state.yml               # Applied state (auto-managed)
├── modules/
│   ├── auth/                   # Embedded modules
│   └── blog/
└── myapp/
    └── settings.py             # Contains mutable module config
```

---

## Schema Definitions

### `quickscale.yml` (Desired State)

```yaml
version: 0.70.0

project:
  name: myapp
  theme: showcase_html

modules:
  auth:
    registration: true           # Mutable
    email_verification: false    # Mutable
    custom_user_model: true      # Immutable
  blog:
    comments: true
    posts_per_page: 20

docker:
  start: true
  build: true
```

### `.quickscale/state.yml` (Applied State)

```yaml
version: 0.70.0
last_applied: "2025-11-28T10:30:00Z"

project:
  name: myapp
  theme: showcase_html
  created_at: "2025-11-28T10:00:00Z"

modules:
  auth:
    embedded_at: "2025-11-28T10:05:00Z"
    commit_sha: "abc1234"
    immutable:
      custom_user_model: true
    mutable:
      registration: true
      email_verification: false
```

### Module Manifest (`module.yml`)

```yaml
name: auth
version: 0.70.0

config:
  mutable:                       # Can change after embed
    registration:
      type: boolean
      default: true
      setting: AUTH_REGISTRATION_ENABLED
    email_verification:
      type: boolean
      default: false
      setting: AUTH_EMAIL_VERIFICATION

  immutable:                     # Cannot change after embed
    custom_user_model:
      type: boolean
      default: true
      warning: "Affects database schema"
```

---

## State Management

**Hybrid Approach (Terraform-style)**:
1. **State file** (`.quickscale/state.yml`): Tracks applied configuration
2. **Filesystem verification**: Double-checks modules exist in `modules/`

**Apply logic**:
1. Read desired state from `quickscale.yml`
2. Read applied state from `.quickscale/state.yml`
3. Verify filesystem matches state file
4. Calculate delta (what's new, changed, or removed)
5. Apply only the delta

---

## Configuration Mutability

Following Terraform's pattern:

| Type | Storage | Can Change? | How to Change |
|------|---------|-------------|---------------|
| **Mutable** | `settings.py` | ✅ Yes | Edit YAML → apply |
| **Immutable** | Generated code | ❌ No | Remove module → re-embed |

**Mutable config update**:
```
quickscale apply
→ Detects email_verification: false → true
→ Updates settings.py: AUTH_EMAIL_VERIFICATION = True
→ Restarts Docker
```

**Immutable config change attempt**:
```
quickscale apply
→ Detects custom_user_model: true → false (IMMUTABLE)
→ Error: "Cannot change immutable config"
→ Suggests: quickscale remove auth → edit YAML → apply
```

---

## Execution Order

When `quickscale apply` runs on a new project:

1. Generate project
2. Initialize git + initial commit
3. For each module:
   - Embed module with config
   - `git add -A && git commit`
4. `poetry install`
5. `python manage.py migrate`
6. `quickscale up --build` (if docker.start: true)

**This order is fixed** — there's only one correct sequence.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Directory exists | Error + suggest `--force` or different name |
| Module already embedded | Skip (no change) |
| Immutable config changed | Error + suggest remove/re-embed |
| Git has uncommitted changes | Warning + ask to continue |
| Docker not running | Skip restart + show instructions |

---

## References

- **Decisions**: [decisions.md](./decisions.md)
- **Roadmap**: [roadmap.md](./roadmap.md) (v0.68.0-v0.71.0)
- **User Manual**: [user_manual.md](./user_manual.md)
