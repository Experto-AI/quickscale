# React Default + E2E Parity Implementation Plan

## 1. Objective
Align the codebase so React (`showcase_react`) is the true default theme in generation and config fallback paths, and ensure deep PostgreSQL + Playwright lifecycle E2E coverage runs for both React and HTML themes.

This plan is written for direct handoff and execution by another engineer/agent without additional product decisions.

---

## 2. Success Criteria
A task is complete only when all of the following are true:

1. `ProjectGenerator()` defaults to `showcase_react`.
2. Omitted `project.theme` in config parsing resolves to `showcase_react`.
3. CLI fallback paths that infer theme without explicit config also resolve to `showcase_react`.
4. Full lifecycle E2E coverage (generate -> deps -> postgres migrate/check/static -> server -> Playwright browser checks) exists and passes for:
   - React theme
   - HTML theme
5. Existing explicit HTML tests remain as compatibility checks (do not remove HTML support).
6. All impacted tests are updated and passing.

---

## 3. Non-Goals
1. No removal of `showcase_html` support.
2. No changes to theme list/validation (`showcase_html`, `showcase_htmx`, `showcase_react` remain valid).
3. No redesign of CLI UX text beyond what is necessary to keep default references accurate.
4. No changes to generator template content except where test behavior requires explicit theme selection.

---

## 4. Current State Summary
Observed mismatches:

1. Product/decision docs and plan UX indicate React default.
2. Core generator default is still HTML.
3. CLI schema fallback default is still HTML.
4. Reconfigure fallback default in plan command is still HTML.
5. E2E suite includes strong React tests, but the deepest PostgreSQL + Playwright lifecycle flow currently relies on implicit default generator usage in key places.

---

## 5. Required Code Changes (File-by-File)

## 5.1 Core default theme switch
### File
`quickscale_core/src/quickscale_core/generator/generator.py`

### Changes
1. Update `ProjectGenerator.__init__` signature:
   - from `theme: str = "showcase_html"`
   - to `theme: str = "showcase_react"`
2. Update docstring text that currently says default is HTML.
3. Keep `available_themes` unchanged.

### Rationale
Makes generator behavior match documented product default and CLI plan expectation.

---

## 5.2 CLI config schema fallback switch
### File
`quickscale_cli/src/quickscale_cli/schema/config_schema.py`

### Changes
1. Update dataclass default:
   - `ProjectConfig.theme` from `showcase_html` -> `showcase_react`.
2. Update parsing fallback:
   - `_validate_project_section`: `project_data.get("theme", "showcase_react")`.
3. Update suggestion/help strings that show fallback examples so they reference `showcase_react`.

### Rationale
Ensures omitted-theme configs parse consistently with intended default behavior.

---

## 5.3 Plan reconfigure fallback switch
### File
`quickscale_cli/src/quickscale_cli/commands/plan_command.py`

### Changes
1. Update `_get_project_info_for_reconfig` final fallback return value:
   - from `(project_path.name, "showcase_html")`
   - to `(project_path.name, "showcase_react")`.

### Rationale
Keeps all fallback logic consistent when state/config are missing or partial.

---

## 5.4 Lifecycle E2E parity (React + HTML)
### Primary file
`quickscale_core/tests/test_e2e_full_workflow.py`

### Required behavior
Ensure full lifecycle path exists for both themes, explicitly and unambiguously.

### Implementation guidance
1. Keep one lifecycle test that verifies default path using `ProjectGenerator()`:
   - This test must now be React by default.
2. Add or refactor lifecycle coverage to explicitly run equivalent flow for HTML:
   - `ProjectGenerator(theme="showcase_html")`.
3. For React lifecycle path, ensure frontend build step is included before static/browsing assertions where required.
4. Avoid brittle cross-theme assertions:
   - Keep generic browser assertions (status/body/title/static link checks) for both.
   - Keep React route-specific checks in React-specific lifecycle tests.
5. Ensure postgres setup (`test_e2e.py`) works identically for both paths.

### Minimum parity checklist per theme
For each theme lifecycle test:
1. Generate project
2. Install dependencies
3. Configure postgres test settings
4. Django check
5. Migrate
6. Collectstatic
7. Start server
8. Playwright request/page assertions
9. Graceful cleanup of server process

---

## 5.5 Explicit-theme pinning in non-default-focused tests
### Files to audit and adjust intentionally
1. `quickscale_core/tests/test_integration.py`
2. `quickscale_cli/tests/test_e2e_development_workflow.py`
3. Any other test file where `ProjectGenerator()` is used but theme is not the thing being tested

### Rule
If a test is not validating default theme behavior, pin theme explicitly (`showcase_html` or `showcase_react`) to avoid accidental semantic drift from future default changes.

### Rationale
Prevents unrelated tests from failing due to implicit default behavior changes.

---

## 6. Required Test Updates (Assertions/Expectations)

## 6.1 Theme default tests
### File
`quickscale_core/tests/generator/test_themes.py`

### Updates
1. `test_default_theme` should expect `showcase_react`.
2. Any test narrative/comments that state default is HTML should be updated.
3. Keep explicit HTML generation tests as compatibility coverage.

---

## 6.2 CLI schema and command tests
### Candidate files
1. `quickscale_cli/tests/test_schema.py`
2. `quickscale_cli/tests/test_plan_reconfigure.py`
3. Any tests asserting omitted theme fallback values

### Updates
1. Default/fallback expectation values should change from `showcase_html` to `showcase_react` where the code path is implicit default.
2. Keep explicit `showcase_html` input tests unchanged.

---

## 7. Validation Strategy

## 7.1 Fast, targeted validation (run first)
1. `poetry run pytest quickscale_core/tests/generator/test_themes.py`
2. `poetry run pytest quickscale_cli/tests/test_schema.py`
3. `poetry run pytest quickscale_cli/tests/test_plan_reconfigure.py`
4. `poetry run pytest quickscale_core/tests/test_integration.py`

## 7.2 Lifecycle validation
1. `poetry run pytest quickscale_core/tests/test_e2e_full_workflow.py -m e2e -q`
   - Confirm both React and HTML deep lifecycle tests execute.

## 7.3 CLI/React E2E validation
1. `poetry run pytest quickscale_cli/tests/test_react_theme_e2e.py -m e2e -q`
2. `poetry run pytest quickscale_cli/tests/test_e2e_development_workflow.py -m e2e -q`

## 7.4 End-to-end script validation
1. `./scripts/test_e2e.sh --full`

---

## 8. Acceptance Test Matrix

| Area | Scenario | Expected |
|---|---|---|
| Generator default | `ProjectGenerator()` | `theme == showcase_react` |
| Generator explicit HTML | `ProjectGenerator(theme=\"showcase_html\")` | HTML files generated correctly |
| Config parsing fallback | `project.theme` omitted in YAML | parsed theme is `showcase_react` |
| Reconfigure fallback | no state/config edge fallback | fallback theme is `showcase_react` |
| Core lifecycle E2E (React) | full postgres+playwright | pass |
| Core lifecycle E2E (HTML) | full postgres+playwright | pass |
| React CLI E2E | plan/apply/build/lint/docker | pass/skip only for known env dependency cases |
| Existing explicit HTML tests | explicit HTML theme inputs | still pass |

---

## 9. Risk Register and Mitigations

## Risk 1: Runtime increase in E2E due to dual deep lifecycle
Mitigation:
1. Keep tests deterministic and avoid redundant heavy setup.
2. Reuse helper methods and avoid unnecessary frontend builds in HTML path.

## Risk 2: Fragile assertions after default switch
Mitigation:
1. Pin theme explicitly in tests that are not about default behavior.
2. Restrict default assertions to dedicated default-behavior tests.

## Risk 3: Network-related flakes (pnpm/PyPI)
Mitigation:
1. Preserve existing skip logic for registry connectivity checks.
2. Avoid introducing new external network dependencies.

---

## 10. Execution Order (Recommended)
1. Update generator default (`generator.py`).
2. Update CLI schema defaults/fallbacks (`config_schema.py`).
3. Update reconfigure fallback (`plan_command.py`).
4. Refactor/add lifecycle E2E parity in `test_e2e_full_workflow.py`.
5. Update default-related tests (`test_themes.py`, schema/plan tests).
6. Audit and pin non-default tests that use implicit `ProjectGenerator()`.
7. Run targeted tests.
8. Run E2E validations.
9. Run `scripts/test_e2e.sh --full` final confirmation.

---

## 11. Definition of Done Checklist
1. All code changes in Sections 5.1-5.5 completed.
2. All expected test updates in Section 6 completed.
3. Validation commands in Section 7 executed with pass criteria met.
4. No regressions in explicit HTML support.
5. Commit includes concise summary with:
   - default switch details
   - E2E parity details
   - test evidence

---

## 12. Suggested Commit Breakdown (Optional)
1. Commit 1: "feat(core,cli): switch implicit theme defaults to showcase_react"
2. Commit 2: "test(core): add/align full lifecycle e2e parity for react and html"
3. Commit 3: "test: update default-theme assertions and pin non-default tests"

This split keeps behavior changes, deep E2E refactor, and test expectation updates reviewable.
