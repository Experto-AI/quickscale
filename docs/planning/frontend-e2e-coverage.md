# Frontend E2E Coverage — Status, Gap Analysis, and Options

> **Status:** Pre-decision analysis. Not roadmap truth, not an implementation plan.
> **Purpose:** Give the maintainer enough evidence to choose a direction, then derive a ticket.
> **Authoritative sources:** [roadmap.md](../technical/roadmap.md) (open work) | [validation_policy.md](../technical/validation_policy.md) (command authority) | [decisions.md](../technical/decisions.md) (policy) | [CHANGELOG.md](../../CHANGELOG.md) (closed work)
> **Investigated at:** branch `v87`, commit `e1597ebf`, 2026-08-20.

## 1. The question this answers

Two questions were asked:

1. Is there a Playwright suite that exercises **all pages and links** of the default React theme (`showcase_react`)?
2. Is there a **test plan expressed as user stories or case studies**?

Short answers: **no** and **no**. The longer answer is that the gap is narrower than it first appears, because the jsdom layer already covers routing well. What is missing is specifically *real browser against a real backend*, and *a named set of journeys* to test against.

## 2. Current state — what exists today

### 2.1 Four distinct layers exist, and they are often confused with each other

| Layer | Location | Runner | What it actually proves |
|---|---|---|---|
| A. Generation tests | `quickscale_cli/tests/test_react_theme_e2e.py` (731 lines) | pytest `-m e2e` | `plan`→`apply` produces a project whose `package.json`/`tsconfig`/`vite.config` are valid and whose `pnpm install / lint / type-check / build` succeed. **No browser.** |
| B. Component/route tests | theme `src/test/*.tsx` (~1150 lines) | vitest (jsdom) | Route table mounts correctly per module flag; public social pages render payload states; root dispatch picks the right surface. |
| C. Repo browser E2E | `quickscale_core/tests/test_e2e_full_workflow.py` (2068 lines) | pytest-playwright, `.github/workflows/e2e.yml` | The served app returns 200, has a title, has a visible body, and its first stylesheet loads. |
| D. Generated-project Playwright | theme `playwright.config.ts` + `e2e/home.spec.ts.j2` | `pnpm test:e2e` | Two assertions — page title, one welcome string. **Never executed by any CI.** |

### 2.2 Layer B is stronger than expected

`src/test/App.test.tsx` already asserts, in jsdom, that: the org list shell mounts in saas mode; module routes do **not** mount when their flag is false; `blog`/`crm` mount only when enabled; unselected module routes fall through to the not-found fallback; `/settings` and `/profile` mount unconditionally. `RootDispatch.test.tsx` covers the public-surface injector shapes including a hard failure when required module keys are absent.

This matters for scoping: **route-mounting logic is already covered.** Duplicating it in Playwright buys little. The uncovered thing is whether a mounted page *survives contact with a real API response*.

### 2.3 Layer C is thinner than its name suggests

The browser assertions in `test_e2e_full_workflow.py` are three private helpers:

- `_test_homepage_loads` — `response.status == 200`
- `_test_page_content` — `page.title()` truthy, `body.is_visible()`
- `_test_static_files_load` — first `link[rel=stylesheet]` returns 200

Plus `_test_react_routes_render`, which despite its name **uses `urllib`, not the browser**. It fetches `/`, `/settings`, and a deliberately bogus route and asserts the HTML contains `<div id="root"></div>` and a `frontend/assets/index` reference. That is a check on Django's SPA catch-all, not on React. A route whose component throws on mount passes all four helpers.

### 2.4 Layer D is scaffolded and orphaned

- Emitted via `generator.py:63` (`"e2e": "frontend/e2e"`).
- The generated CI (`templates/github/workflows/ci.yml.j2`) runs `pnpm lint`, `pnpm type-check`, `pnpm test:coverage` — **not `pnpm test:e2e`**. Confirmed by grep; there is no Playwright step.
- `home.spec.ts.j2` asserts `Welcome to your {{ project_name }} dashboard` at `/`. But `App.tsx:39` redirects `/` to an org destination in saas mode. The stub is **probably already stale** against the default configuration — and nothing would tell us, because nothing runs it.

This is the sharpest finding in this document: we ship users a Playwright harness that has never been run, containing an assertion we have reason to believe is wrong.

### 2.5 Route inventory versus coverage

From `App.tsx`, saas mode declares: `/` (redirect), `/orgs`, `/orgs/new`, `/orgs/:orgSlug` (index), `.../blog`, `.../listings`, `.../members`, `.../settings`, `/crm`, `/profile`, `/blog`+`/listings` legacy redirects, `/forms`, `/forms/:slug`, `/settings` legacy redirect, `*`. Non-saas mode declares a parallel simpler set. Backing pages: `Dashboard`, `BlogPage`, `CrmPage`, `FormsPage`, `ListingsPage`, `NotFound`, `ProfilePage`, `SettingsPage`, `SocialEmbedsPublicPage`, `SocialLinkTreePublicPage`, plus six under `pages/orgs/`.

Real-browser coverage touches **three** URLs, and only at the HTTP-shell level. Link/navigation coverage — clicking through `Sidebar.tsx`/`Header.tsx` — is **zero** at every layer.

### 2.6 No journey-level test plan exists

`grep -in "user stor|case stud|test plan|acceptance criteria"` across `docs/` returns nothing in `validation_policy.md` or `roadmap.md`. `validation_policy.md:106` names `pytest-playwright` as the browser tool and lists "Frontend regression testing" as a when-required trigger, but no document names *which* flows constitute that regression. The closest artifact, `TestReactThemeUserWorkflow`, is a **generation** workflow (plan → apply → inspect files), not an in-app journey.

Consequence: coverage cannot currently be argued to be complete or incomplete, because there is no denominator.

## 3. Risk framing — why this is worth spending on

- **Shipped-artifact risk (highest).** Every generated project carries a Playwright config and a spec that likely fails on first run. A user running `pnpm test:e2e` on a fresh project gets a red suite from our template. That is a first-impression defect in the product, not an internal testing gap.
- **Silent render regressions.** Generator/template changes are exactly the trigger `validation_policy.md` names for frontend regression testing, yet the current gate cannot detect a page that mounts and throws.
- **Module-matrix combinatorics.** Twelve selectable modules gate routes. jsdom covers flag→route mounting; nothing covers flag→page actually rendering against the real API.
- **Un-tested navigation chrome.** `Sidebar`/`Header` link targets are unverified anywhere. A sidebar link pointing at a removed route is currently undetectable.

## 4. Alternatives

Framed as five options. They are largely composable; the note under each says so.

### Option 1 — Fix and wire the shipped stub (minimum credible)
Correct `home.spec.ts.j2` to match actual default routing, and add a `pnpm test:e2e` step to `ci.yml.j2` so generated projects run it.

- **Buys:** removes the ship-broken-tests defect; gives users a working harness to extend.
- **Costs:** small. One template fix, one CI step, plus Playwright browser install time in the generated project's CI.
- **Leaves open:** our own coverage. We still would not run it in *this* repo's gates.
- **Composable with:** everything. This is arguably a prerequisite for the others.

### Option 2 — Route-sweep smoke in the repo's own E2E
Add a Playwright test in `test_e2e_full_workflow.py` that enumerates the routes for the generated configuration, visits each in a real browser, and asserts: non-empty `#root`, no error-boundary/fallback text, and no `console.error`/`pageerror`.

- **Buys:** catches the exact class the current helpers miss — mounted-but-crashing pages — across all routes, cheaply.
- **Costs:** moderate. Needs a route list that will not silently drift from `App.tsx`, and needs the app in a state where routes are reachable (see §5 open questions).
- **Risk:** a hand-maintained URL list rots. Prefer deriving it, or gate on a test that fails when `App.tsx` route count changes.
- **Composable with:** 1, 3, 4, 5.

### Option 3 — Link-crawler
Instead of enumerating routes, crawl: start at `/`, collect every in-app `href`, visit each once, assert each resolves to a non-`NotFound` page and emits no console error.

- **Buys:** covers navigation chrome, which nothing covers today; self-updating as routes change; catches dead sidebar links.
- **Costs:** moderate. Crawlers need care around auth walls, destructive links, and pagination to stay deterministic.
- **Risk:** flakiness and unbounded runtime if not depth-capped and allowlisted.
- **Composable with:** 1, 4, 5. Partially overlaps 2 — a crawler finds linked routes; a sweep finds *unlinked* ones too. Doing both is defensible; doing only one, the crawler is the better single pick if navigation confidence matters more than exhaustiveness.

### Option 4 — Write the journey document first
Author a user-story / case-study document (`docs/technical/` or here) naming the flows that constitute "the React theme works": e.g. *land on app → see org context → open each nav destination → create an org → invite/list members → change a setting → visit an enabled module page → hit an unknown URL and get NotFound*. Then make each story an explicitly-named test.

- **Buys:** the missing denominator. Coverage becomes arguable. Tests get names a human can review. It also directly answers the second half of the original question.
- **Costs:** low in effort, high in decision-load — it forces choices about what the theme is *for*.
- **Leaves open:** all execution. This is a spec, not a gate.
- **Composable with:** all. **This is the option that most changes the shape of the others**, because it determines what 2/3/5 should assert.

### Option 5 — Full journey E2E against a live stack
Drive real flows (org creation, member list, settings mutation) in a real browser against the Docker-composed stack, asserting on outcomes rather than just absence of errors.

- **Buys:** the only option that proves the product works, not merely that it renders.
- **Costs:** high. Needs auth/session setup, seeded data, and DB state isolation. Note `SA135` (owned PostgreSQL lifecycle) and `SA142` (E2E Docker image reuse) are already in the v88 backlog and are effectively **prerequisites** — journey tests would land on infrastructure the roadmap already acknowledges as unowned.
- **Risk:** highest flake surface; slowest gate. `validation_policy.md` budgets 5–10 min for the full E2E suite; this would strain that.
- **Composable with:** 1, 4. Supersedes much of 2/3 if fully realized.

### Option 0 — Do nothing (stated for honest comparison)
Accept the current posture. Defensible only if the React theme is considered demo-grade scaffolding rather than a supported surface. It is **not** defensible while we ship a Playwright harness that has never been executed — Option 1 is the floor.

## 5. Open questions the maintainer must resolve

These change the answer materially and cannot be settled from the code alone:

1. **Is `showcase_react` a supported product surface or a demo?** Determines whether Option 5 is ever worth it.
2. **Is there auth in front of the app?** No login/signup route appears in `App.tsx`. If Django handles auth upstream, every browser test needs a session strategy — this is the single largest unknown for Options 2/3/5.
3. **Which module matrix is canonical for testing?** All twelve enabled, the default set, or a small matrix? Drives runtime cost directly.
4. **Where does the gate live** — the repo's `e2e.yml`, the generated project's `ci.yml.j2`, or both? They protect different things: ours protects the template, theirs protects the user.
5. **Does journey coverage wait on `SA135`/`SA142`?** If yes, Option 5 is v88-backlog-dependent by construction and only 1–4 are near-term.

## 6. A defensible default, if a recommendation is wanted

Sequence **1 → 4 → 3 (or 2)**, defer **5** behind `SA135`/`SA142`.

Rationale: Option 1 fixes a defect we are actively shipping and is nearly free. Option 4 is cheap and makes every later choice better-posed. Option 3 buys the largest genuine coverage increase per unit of flake risk, and unlike Option 2 it does not introduce a hand-maintained list that will rot. Option 5 is the right end state but lands on infrastructure the roadmap already flags as unowned, so pulling it forward would mean building that infrastructure implicitly and unreviewed.

This is a starting position for iteration, not a decision.

## 7. Evidence index

- `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/` — `playwright.config.ts`, `e2e/home.spec.ts.j2`, `package.json.j2` (`test:e2e`), `src/App.tsx` (route table), `src/test/*`
- `quickscale_core/src/quickscale_core/generator/generator.py:63` — `"e2e": "frontend/e2e"` emission mapping
- `quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2` — generated CI; no Playwright step
- `quickscale_core/tests/test_e2e_full_workflow.py` — `_test_homepage_loads`, `_test_page_content`, `_test_static_files_load`, `_test_react_routes_render`
- `quickscale_cli/tests/test_react_theme_e2e.py` — generation-level workflow tests
- `.github/workflows/e2e.yml` — repo E2E gate, Playwright chromium install
- `docs/technical/validation_policy.md` — E2E policy and tech stack
