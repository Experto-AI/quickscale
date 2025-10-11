# AI Code Task Handoff

## Current Task: Integrate AI Assistant Rules into Prompt System

Context: Need to integrate the AI assistant rules from quickscale-legacy into the quickscale prompt system. The key insight is that **AI assistants don't follow big files with many rules**, so we need **focused, stage-specific files**.

---

## 🎯 RECOMMENDED APPROACH: Focused Stage Files + Shared Principles

### **Structure Aligned with Workflow Stages:**

```
quickscale/
├── docs/
│   ├── contrib/
│   │   ├── contributing.md               # Index/navigation
│   │   ├── plan.md                       # Stage 1: Roadmap planning + pre-task review
│   │   ├── code.md                       # Stage 2: Implementation rules
│   │   ├── review.md                     # Stage 3: Code review checklist
│   │   ├── testing.md                    # Stage 4: Test generation
│   │   ├── debug.md                      # Stage 5: Debugging workflow
│   │   └── shared/
│   │       ├── code_principles.md       # SOLID, DRY, KISS, Explicit Failure
│   │       ├── architecture_guidelines.md # Tech stack, boundaries
│   │       ├── testing_standards.md     # Test structure, mocking, isolation
│   │       ├── task_focus_guidelines.md # Scope discipline
│   │       └── documentation_standards.md
│   └── technical/
│       ├── roadmap.md
│       ├── decisions.md
│       └── scaffolding.md
└── .github/
    └── prompts/
        ├── roadmap-plan-review-and-update.prompt.md       → refs plan.md
        ├── roadmap-task-implementation.prompt.md          → refs code.md + testing.md
        ├── release-commit-message-and-roadmap-cleaning.prompt.md → refs review.md
        └── [future] debug-failing-tests.prompt.md         → refs debug.md
```

---

## **How Each Stage File Maps to Workflow:**

### **1. plan.md** (Roadmap Planning + Pre-Task Review)
**Purpose:** Plan roadmap strategy from scratch AND review/adjust specifications before each task/sprint.

**Key Sections:**
- Understanding project context (READ first: decisions.md, scaffolding.md, README.md)
- Breaking down features into tasks
- Defining clear task boundaries and deliverables
- Pre-task review checklist (validate task is still in scope, no conflicts with decisions.md)
- Planning for testability and architecture compliance

**Referenced by prompts:**
- `roadmap-plan-review-and-update.prompt.md` (primary)
- `roadmap-task-implementation.prompt.md` (pre-implementation review step)

**References shared principles:**
- `shared/architecture_guidelines.md` - tech stack validation
- `shared/task_focus_guidelines.md` - scope discipline
- `shared/code_principles.md#planning-application` - SOLID/DRY/KISS planning

---

### **2. code.md** (Implementation)
**Purpose:** Create code following decisions.md, technical boundaries, code rules, and roadmap scope.

**Key Sections:**
- Apply SOLID principles during implementation
- Apply DRY, KISS, Explicit Failure patterns
- Code structure and organization
- Type hints and documentation rules
- **Strict scope enforcement** (implement ONLY what's in the task checklist)

**Referenced by prompts:**
- `roadmap-task-implementation.prompt.md` (primary)

**References shared principles:**
- `shared/code_principles.md` - SOLID, DRY, KISS implementation patterns
- `shared/architecture_guidelines.md` - layer boundaries, tech stack adherence
- `shared/documentation_standards.md` - docstring format
- `shared/task_focus_guidelines.md` - prevent scope creep

---

### **3. review.md** (Quality Control)
**Purpose:** Review generated code against guidelines, technical boundaries, and roadmap scope BEFORE writing tests.

**Key Sections:**
- Verify technical stack compliance
- Verify architectural pattern compliance
- Verify SOLID/DRY/KISS adherence
- Verify scope compliance (no out-of-scope features added)
- Verify documentation completeness
- Pre-commit checklist

**Referenced by prompts:**
- `roadmap-task-implementation.prompt.md` (self-review step after coding, before testing)
- `release-commit-message-and-roadmap-cleaning.prompt.md` (final message and cleanup before release)

**References shared principles:**
- `shared/code_principles.md#quality-control-application`
- `shared/architecture_guidelines.md#quality-control-stage`
- `shared/task_focus_guidelines.md#validation-and-review`

---

### **4. testing.md** (Test Generation)
**Purpose:** Generate unit/integration tests AFTER implementation is complete AND reviewed.

**Key Sections:**
- **Implementation-first testing approach** (write tests after code is reviewed)
- Test structure and organization (group by functionality)
- Behavior-focused testing (test contracts, not internals)
- Mock usage for isolation
- **NO GLOBAL MOCKING** (prevent contamination)
- Test parameterization
- Arrange-Act-Assert pattern

**Referenced by prompts:**
- `roadmap-task-implementation.prompt.md` (after code.md and review.md stages)

**References shared principles:**
- `shared/testing_standards.md` - all test rules

---

### **5. debug.md** (Debugging Workflow)
**Purpose:** Debug issues and failing test code using systematic root cause analysis.

**Key Sections:**
- Root cause analysis (never mask symptoms)
- DMAIC process (Define, Measure, Analyze, Improve, Control)
- Debugging failing tests (is test wrong or code wrong?)
- Minimal fixes (address root cause, not symptoms)
- Add regression tests after fixing

**Referenced by prompts:**
- [Future] `debug-failing-tests.prompt.md`
- Can be invoked manually when tests fail

**References shared principles:**
- `shared/code_principles.md#debugging-application`
- `shared/testing_standards.md` - test isolation debugging

---

## **How Prompts Reference Stage Files:**

### **Example: roadmap-task-implementation.prompt.md**

```markdown
AUTHORITATIVE CONTEXT (READ BEFORE CODING)
------------------------------------------------
**Project Context:**
1) Roadmap: `docs/technical/roadmap.md` — task checklist and deliverables
2) Scope decisions: `docs/technical/decisions.md` — what's IN vs OUT of scope
3) Scaffolding: `docs/technical/scaffolding.md` — directory layout
4) General understanding: `README.md`

**Development Stages (follow in order):**
5) Planning stage: `docs/contrib/plan.md` — review task scope before coding
6) Implementation stage: `docs/contrib/code.md` — coding rules and patterns
7) Review stage: `docs/contrib/review.md` — verify compliance after coding
8) Testing stage: `docs/contrib/testing.md` — generate tests AFTER review

**Shared Principles (referenced by stage files):**
- Code principles: `docs/contrib/shared/code_principles.md`
- Architecture: `docs/contrib/shared/architecture_guidelines.md`
- Testing standards: `docs/contrib/shared/testing_standards.md`
- Task focus: `docs/contrib/shared/task_focus_guidelines.md`

WORKFLOW (follow these stages)
-------------------------------
1. **PLAN**: Read plan.md and review the task scope against roadmap/decisions.md
2. **CODE**: Read code.md and implement following all rules
3. **REVIEW**: Read review.md and self-review the implementation
4. **TEST**: Read testing.md and generate tests (after code review is complete)
5. **DEBUG**: If tests fail, read debug.md and apply root cause analysis
```

---

## **Key Advantages of This Approach:**

### ✅ **Solves the "Big File Problem"**
- Each stage file is **focused and digestible** (~200-400 lines max)
- AI assistant only reads **relevant stage file** for current task
- Shared principles are **referenced, not duplicated**

### ✅ **Enforces Workflow Stages**
- Prompts explicitly list stage files in order
- Forces AI to follow **PLAN → CODE → REVIEW → TESTING → DEBUG** flow
- Prevents skipping stages (e.g., writing tests before code review)

### ✅ **Maintains Single Source of Truth**
- Shared principles (SOLID, DRY, KISS) defined once in `shared/`
- Each stage file references appropriate sections
- No duplication = easier maintenance

### ✅ **Prompt Flexibility**
- Each prompt references **only the stages it needs**
- `roadmap-plan-review-and-update.prompt.md` → only plan.md
- `roadmap-task-implementation.prompt.md` → plan.md + code.md + review.md + testing.md
- `debug-failing-tests.prompt.md` → only debug.md

### ✅ **Scalable**
- Add new stages (e.g., deploy.md) without bloating existing files
- Add new prompts (e.g., refactor-legacy-code.prompt.md) that reference appropriate stages

---

## Development Workflow Stages

Follow these stages in order for any code change:

1. **[PLAN](docs/contrib/plan.md)** - Plan roadmap or review task scope
2. **[CODE](docs/contrib/code.md)** - Implement following all rules
3. **[REVIEW](docs/contrib/review.md)** - Self-review implementation for quality
4. **[TESTING](docs/contrib/testing.md)** - Generate tests after code review
5. **[DEBUG](docs/contrib/debug.md)** - Debug issues using root cause analysis

## Shared Principles (Referenced by Stage Files)

- [Code Principles](docs/contrib/shared/code_principles.md) - SOLID, DRY, KISS
- [Architecture Guidelines](docs/contrib/shared/architecture_guidelines.md)
- [Testing Standards](docs/contrib/shared/testing_standards.md)
- [Task Focus Guidelines](docs/contrib/shared/task_focus_guidelines.md)
- [Documentation Standards](docs/contrib/shared/documentation_standards.md)

## Prompts

- [roadmap-task-implementation](.github/prompts/roadmap-task-implementation.prompt.md)
- [roadmap-plan-review-and-update](.github/prompts/roadmap-plan-review-and-update.prompt.md)
- [release-commit-message-and-roadmap-cleaning](.github/prompts/release-commit-message-and-roadmap-cleaning.prompt.md)
```



