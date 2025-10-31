# Release v0.64.0: Theme Rename (`starter_html` → `showcase_html`)

**Release Date**: October 31, 2025 (Target)
**Status**: 🔄 READY FOR IMPLEMENTATION
**Objective**: Atomic, coordinated rename of theme from `starter_html` to `showcase_html` across all code, templates, tests, and documentation

---

## Why v0.64.0 (Theme Rename First)?

**Strategic Decision**: The theme rename is MANDATORY and must happen before showcase features are added in v0.65.0.

**Rationale**:
1. **Brand Clarity**: "Showcase HTML" better reflects the theme's purpose (demonstrating module capabilities)
2. **Future-Proof**: Establishes naming before v0.65.0 adds actual showcase features
3. **Low Risk**: Single-purpose release, easy to test and rollback if needed
4. **Clean History**: Separates rename from feature work for clearer git history
5. **Atomic Operation**: All renames happen together in one commit, avoiding partial state

**Approach**: This is a **surgical refactoring release** - no feature changes, only renaming for consistency.

---

## Scope Boundaries

### ✅ IN SCOPE (v0.64.0)
- Rename filesystem directory: `themes/starter_html/` → `themes/showcase_html/`
- Update generator defaults and theme resolution logic
- Update all authoritative docs (decisions.md, scaffolding.md, user_manual.md, README.md)
- Update CLI tests and generator tests
- Single atomic commit with all changes together

### ❌ OUT OF SCOPE (Deferred)
- Showcase features (landing page, module cards, preview pages) → v0.65.0
- Auth module changes (stable from v0.63.0)
- New modules or theme variants
- Email verification (v0.66.0)
- Any functional changes beyond renaming

---

## Implementation Tasks (Atomic Commit)

Execute all tasks in sequence, then commit as single atomic change.

### Task Group 1: Filesystem Rename
- [ ] **Backup current state**: Create git branch `v64-theme-rename`
- [ ] **Rename directory**:
  ```bash
  cd quickscale_core/src/quickscale_core/generator/templates/themes/
  mv starter_html showcase_html
  ```
- [ ] **Verify structure**: Ensure all subdirectories moved correctly
  - [ ] `showcase_html/templates/` exists
  - [ ] `showcase_html/static/` exists
  - [ ] All `.html.j2` files present

**Files affected**: All files under `themes/starter_html/` moved to `themes/showcase_html/`

---

### Task Group 2: Generator Code Updates

**File**: `quickscale_core/src/quickscale_core/generator/generator.py` (or equivalent)

- [ ] **Update default theme**:
  ```python
  # OLD
  def __init__(self, project_name: str, theme: str = "starter_html"):

  # NEW
  def __init__(self, project_name: str, theme: str = "showcase_html"):
  ```

- [ ] **Update theme path resolution**:

- [ ] **Search for other occurrences**:
  ```bash
  cd quickscale_core/src
  grep -r "starter_html" . | grep -v ".pyc" | grep -v "__pycache__"
  # Fix all occurrences found
  ```

**Expected changes**: 3-5 lines in generator.py, possible changes in template loader

---

### Task Group 3: CLI Code Updates

**File**: `quickscale_cli/src/quickscale_cli/commands/init.py` (or equivalent)

- [ ] **Check for hardcoded theme references**:
  ```bash
  cd quickscale_cli/src
  grep -r "starter_html" .
  ```

- [ ] **Update any CLI-specific theme validation** (if exists)
- [ ] **Update help text** for `--theme` flag if it lists themes

**Expected changes**: 0-2 lines (CLI likely delegates to generator)

---

### Task Group 4: Test Updates

**Files to update**:
- `quickscale_core/tests/test_generator.py`
- `quickscale_core/tests/test_generator_templates.py`
- `quickscale_cli/tests/test_cli.py`
- `quickscale_core/tests/test_e2e_full_workflow.py` (if exists)

**Search and replace**:
```bash
cd quickscale_core/tests
grep -r "starter_html" . | grep -v ".pyc" | grep -v "__pycache__"

cd quickscale_cli/tests
grep -r "starter_html" . | grep -v ".pyc" | grep -v "__pycache__"
```

**For each test file**:
- [ ] Replace `"starter_html"` with `"showcase_html"` in:
  - [ ] Test fixtures
  - [ ] Assertion expectations
  - [ ] Path validations
  - [ ] CLI command invocations

**Example changes**:
```python
# OLD
def test_default_theme():
    assert generator.theme == "starter_html"

# NEW
def test_default_theme():
    assert generator.theme == "showcase_html"
```

**Expected changes**: 10-20 lines across test files

---

### Task Group 5: Documentation Updates (Authoritative)

All documentation must be updated in the SAME commit as code changes.

#### File 1: `docs/technical/decisions.md`

**Search for occurrences**:
```bash
grep -n "starter_html" docs/technical/decisions.md
```

**Update sections**:
- [ ] Line 156: Theme directory structure examples
- [ ] Line 181: Theme tree structure
- [ ] Line 348: MVP Feature Matrix theme CLI flag
- [ ] Line 365: Themes IN scope table
- [ ] Line 431: CLI commands reference
- [ ] Line 433: Template refactoring notes

**Example change**:
```diff
-1. Store themes in `quickscale_core/generator/templates/themes/{starter_html,starter_htmx,starter_react}/`
+1. Store themes in `quickscale_core/generator/templates/themes/{showcase_html,starter_htmx,starter_react}/`
```

---

#### File 2: `docs/technical/scaffolding.md`

**Search for occurrences**:
```bash
grep -n "starter_html" docs/technical/scaffolding.md
```

**Update sections**:
- Theme directory structure examples
- Post-MVP structure diagrams
- Generated project references

**Note**: Do NOT update historical release document references (preserve accuracy)

---

#### File 3: `docs/technical/user_manual.md`

**Search for occurrences**:
```bash
grep -n "starter_html" docs/technical/user_manual.md
```

**Update sections**:
- [ ] Theme selection CLI examples
- [ ] Available themes list
- [ ] Quick start examples

**Example change**:
```diff
-# Default HTML theme (production-ready)
-quickscale init myapp
-quickscale init myapp --theme starter_html
+# Default Showcase HTML theme (production-ready)
+quickscale init myapp
+quickscale init myapp --theme showcase_html
```

---

#### File 4: `README.md`

**Search for occurrences**:
```bash
grep -n "starter_html" README.md
```

**Update sections**:
- [ ] Quick Start theme selection examples
- [ ] Development Flow section
- [ ] Available themes list

**Example change**:
```diff
# Or choose a specific theme (v0.61.0+)
-# quickscale init myapp --theme starter_html  # Default HTML theme
+# quickscale init myapp --theme showcase_html  # Default Showcase HTML theme
 # quickscale init myapp --theme starter_htmx  # HTMX theme (coming in v0.67.0)
```

---

### Task Group 6: Validation & Quality Gates

**Run all quality checks BEFORE committing**:

#### Linting
```bash
cd quickscale_core
poetry run ruff format .
poetry run ruff check .

cd ../quickscale_cli
poetry run ruff format .
poetry run ruff check .
```

#### Type Checking
```bash
cd quickscale_core
poetry run mypy src/

cd ../quickscale_cli
poetry run mypy src/
```

#### Test Suite
```bash
# Run generator tests
cd quickscale_core
poetry run pytest -v

# Run CLI tests
cd ../quickscale_cli
poetry run pytest -v

# Run full test suite
cd ..
./scripts/test_all.sh
```

**All tests MUST pass before committing**

---

#### Manual Smoke Tests

**Test 1: Default theme works**
```bash
quickscale init testproject1
cd testproject1
ls -la  # Verify project created
cd ..
rm -rf testproject1
```

**Test 2: Explicit showcase_html works**
```bash
quickscale init testproject2 --theme showcase_html
cd testproject2
ls -la  # Verify project created
cd ..
rm -rf testproject2
```

**Test 3: Invalid theme fails gracefully**
```bash
quickscale init testproject3 --theme starter_html
# Should fail with error: Theme 'starter_html' not found
# Error message should suggest: Available themes: showcase_html, starter_htmx, starter_react
```

**Test 4: Generated project runs**
```bash
quickscale init testproject4
cd testproject4
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver &
sleep 3
curl http://localhost:8000/  # Should return HTML
kill %1
cd ..
rm -rf testproject4
```

---

## Success Criteria (All Must Pass)

### Code Quality
- [ ] ✅ All linting checks pass (Ruff format + check)
- [ ] ✅ All type checks pass (MyPy)
- [ ] ✅ No hardcoded `starter_html` strings remain in source code

### Test Suite
- [ ] ✅ All generator tests pass
- [ ] ✅ All CLI tests pass
- [ ] ✅ Full test suite passes (`./scripts/test_all.sh`)

### Manual Testing
- [ ] ✅ `quickscale init` uses `showcase_html` by default
- [ ] ✅ `quickscale init --theme showcase_html` works
- [ ] ✅ `quickscale init --theme starter_html` fails with clear error message
- [ ] ✅ Generated project runs successfully (manage.py runserver)

### Documentation
- [ ] ✅ decisions.md updated and consistent
- [ ] ✅ scaffolding.md updated and consistent
- [ ] ✅ user_manual.md updated and consistent
- [ ] ✅ README.md updated and consistent
- [ ] ✅ No `starter_html` references in docs (except historical releases)

### Git Hygiene
- [ ] ✅ Single atomic commit with descriptive message
- [ ] ✅ All changes in one commit (no partial state)
- [ ] ✅ Commit message follows convention

---

## Deliverables

1. **Renamed theme directory**: `themes/showcase_html/` (filesystem)
2. **Updated generator code**: Default theme changed to `showcase_html`
3. **Updated test suite**: All tests passing with new theme name
4. **Updated authoritative docs**: decisions.md, scaffolding.md, user_manual.md, README.md
5. **Release documentation**: `docs/releases/release-v0.64.0-implementation.md`

---

## Migration Path

### For Existing Users (v0.61.0-v0.63.0)
- ✅ **Existing generated projects continue working unchanged** (they don't depend on QuickScale after generation)
- ⚠️  **BREAKING**: `--theme starter_html` flag no longer works
- ✅ Users must use `--theme showcase_html` for new projects

### For New Users (v0.64.0+)
- ✅ `quickscale init` uses `showcase_html` theme by default
- ✅ Documentation shows `showcase_html` in all examples
- ✅ Only valid theme name is `showcase_html` (and future themes)

### For Scripts/Automation
- ⚠️  **BREAKING**: Scripts using `--theme starter_html` will fail
- ✅ Update scripts to use `--theme showcase_html`
- ✅ Scripts using default theme (no `--theme` flag) work automatically

---

## Commit Message Template

```
Release v0.64.0: Rename theme from starter_html to showcase_html

BREAKING CHANGE: Theme renamed from starter_html to showcase_html.

Changes:
- Renamed themes/starter_html/ → themes/showcase_html/
- Updated generator default from starter_html to showcase_html
- Updated all authoritative docs (decisions.md, scaffolding.md, user_manual.md, README.md)
- Updated all tests to use showcase_html

Breaking Changes:
- --theme starter_html no longer works (use --theme showcase_html)
- Scripts using --theme starter_html must be updated
- Existing generated projects unaffected (no QuickScale dependency after generation)

Migration:
- Existing projects: No action required (continue working unchanged)
- New projects: Automatically use showcase_html
- Scripts: Update --theme starter_html → --theme showcase_html

Rationale: Establishes "Showcase" branding before v0.65.0 adds actual
showcase features (module cards, preview pages). Clean breaking change
without backward compatibility cruft.

Tested: All tests passing, manual smoke tests completed
```

---

## Next Steps

### After v0.64.0 Release
1. ✅ Commit theme rename with message above
2. ✅ Create `docs/releases/release-v0.64.0-implementation.md` documenting completion
3. ✅ Update roadmap: Move v0.64.0 to "Completed Releases" section
4. ⏭️  Plan v0.65.0 (Showcase Architecture implementation)

### v0.65.0 Planning
- Use `showcase_html` theme name throughout
- Add module showcase features (landing page, preview pages)
- Reference v0.64.0 theme rename as prerequisite

---

## Risk Assessment

### Low Risk Items ✅
- Filesystem rename (straightforward, reversible)
- Generator default change (single line)
- Documentation updates (no code impact)
- Test updates (straightforward search/replace)

### Medium Risk Items ⚠️
- Potential hardcoded paths in templates (need verification)
- Breaking change for users with scripts using `--theme starter_html`

### Mitigation Strategies
1. **Single atomic commit**: Makes rollback easy if issues found
2. **Clear error messages**: Guide users to use `showcase_html` instead
3. **Comprehensive testing**: Manual + automated tests catch issues
4. **Documentation updates**: All docs clearly show new theme name

---

## Timeline Estimate

**Total effort**: 2-3 hours

**Breakdown**:
- Task Group 1 (Filesystem): 15 minutes
- Task Group 2 (Generator Code): 30 minutes
- Task Group 3 (CLI Code): 15 minutes
- Task Group 4 (Tests): 45 minutes
- Task Group 5 (Documentation): 45 minutes
- Task Group 6 (Validation): 30 minutes

**Target completion**: Same day (October 31, 2025)

---

## References

- **Roadmap**: `docs/technical/roadmap.md` (v0.64.0 section)
- **Architecture**: `docs/technical/decisions.md` (Theme & Module Architecture)
- **Structure**: `docs/technical/scaffolding.md` (Theme Directory Layout)
- **Previous Release**: `docs/releases/release-v0.63.0-implementation.md` (Auth Module)
- **Next Release**: `docs/releases/release-v0.65.0-plan.md` (Showcase Architecture)
