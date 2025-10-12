# Review Report: [TASK_ID] - [TASK_NAME]

**Task**: [SHORT_GOAL_STATEMENT]  
**Release**: [RELEASE_VERSION]  
**Review Date**: [YYYY-MM-DD]  
**Reviewer**: [REVIEWER_NAME]

---

## EXECUTIVE SUMMARY

**OVERALL STATUS**: [✅ APPROVED - EXCELLENT QUALITY / ⚠️ APPROVED WITH MINOR ISSUES / ❌ REJECTED - NEEDS REVISION / 🚫 BLOCKED]

[2-3 sentence summary of overall findings, quality assessment, and recommendation]

**Key Achievements**:
- [Major achievement 1]
- [Major achievement 2]
- [Major achievement 3]

---

## 1. SCOPE COMPLIANCE CHECK [✅ / ⚠️ / ❌]

### Deliverables Against Roadmap Checklist

**From roadmap Task [TASK_ID] - [ALL ITEMS COMPLETE / PARTIAL / INCOMPLETE]**:

✅/❌ **[Deliverable Category 1]**:
- [Item 1] ✅/❌
- [Item 2] ✅/❌

✅/❌ **[Deliverable Category 2]**:
- [Item 1] ✅/❌
- [Item 2] ✅/❌

### Scope Discipline Assessment

**[✅ NO SCOPE CREEP DETECTED / ⚠️ MINOR SCOPE DRIFT / ❌ SIGNIFICANT SCOPE CREEP]**

All changes are explicitly listed in the roadmap task [TASK_ID]:
- [List each modified/added file and its purpose]
- [Verify each relates to task deliverables]

**No out-of-scope features added**:
- ❌ No [feature X] (correctly deferred to [version])
- ❌ No [feature Y] (correctly deferred)

**[OR if scope creep detected]:**
⚠️ **SCOPE CREEP DETECTED**:
- [File/feature outside task scope with explanation]

---

## 2. ARCHITECTURE & TECHNICAL STACK COMPLIANCE [✅ / ⚠️ / ❌]

### Technical Stack Verification

**[✅ ALL APPROVED TECHNOLOGIES USED / ⚠️ MINOR DEVIATIONS / ❌ UNAPPROVED TECHNOLOGIES]** (per decisions.md):

**[Technology Category 1]**:
- ✅/❌ [Technology/package with version]
- ✅/❌ [Technology/package with version]

**[Technology Category 2]**:
- ✅/❌ [Technology/package with version]

### Architectural Pattern Compliance

**✅ PROPER [COMPONENT] ORGANIZATION**:
- [Component] located in correct directory: `[path]`
- [Component] naming follows [convention]
- [Component] content uses [pattern] correctly
- No architectural boundaries violated

**✅/❌ TEST ORGANIZATION**:
- Tests in correct location: `[path]`
- Tests organized by [functionality/concern]
- Proper use of [test framework features]
- No global mocking contamination

---

## 3. CODE QUALITY VALIDATION [✅ / ⚠️ / ❌]

### SOLID Principles Compliance

**✅/❌ Single Responsibility Principle**:
- [Assessment of SRP adherence with examples]

**✅/❌ Open/Closed Principle**:
- [Assessment of OCP adherence with examples]

**✅/❌ Dependency Inversion**:
- [Assessment of DIP adherence with examples]

### DRY Principle Compliance

**✅/❌ NO CODE DUPLICATION**:
- [Assessment of code reuse and duplication]

### KISS Principle Compliance

**✅/❌ APPROPRIATE SIMPLICITY**:
- [Assessment of solution complexity]

### Explicit Failure Compliance

**✅/❌ PROPER ERROR HANDLING**:
- [Assessment of error handling patterns]

### Code Style & Conventions

**✅/❌ ALL STYLE CHECKS PASSING**:
```bash
[Output from ./scripts/lint.sh]
```

**✅/❌ DOCSTRING QUALITY**:
- [Assessment of docstring completeness and format]
- [Example of good docstring if applicable]

**✅/❌ TYPE HINTS**:
- [Assessment of type hint usage]

---

## 4. TESTING QUALITY ASSURANCE [✅ / ⚠️ / ❌]

### Test Contamination Prevention

**✅/❌ NO GLOBAL MOCKING CONTAMINATION DETECTED**:
- [Assessment of mocking practices]

**✅/❌ TEST ISOLATION VERIFIED**:
```bash
# Tests pass individually: ✅/❌
# Tests pass as suite: ✅/❌ ([N] passed)
# No execution order dependencies: ✅/❌
```

### Test Structure & Organization

**✅/❌ [EXCELLENT/GOOD/POOR] TEST ORGANIZATION**:

Tests organized into [N] logical test classes:
1. `[TestClassName1]` - [Purpose] ([N] tests)
2. `[TestClassName2]` - [Purpose] ([N] tests)

### Behavior-Focused Testing

**✅/❌ TESTS FOCUS ON BEHAVIOR**:

**Good Example - Testing Observable Behavior**:
```python
[Example of behavior-focused test from codebase]
```

[Explanation of why this is good]

### Test Coverage

**✅/❌ COMPREHENSIVE COVERAGE MAINTAINED**:
```bash
Coverage Report:
- [package1]: [X]% ([N] statements, [M] miss)
- [package2]: [X]% ([N] statements, [M] miss)
- Total: [N] tests passing
```

**✅/❌ ALL IMPORTANT CODE PATHS COVERED**:
- [Category 1] ([N] tests)
- [Category 2] ([N] tests)
- Edge cases ([N] tests)

### Mock Usage

**✅/❌ PROPER MOCK USAGE**:
- [Assessment of mock usage and isolation]

---

## 5. [COMPONENT-SPECIFIC] CONTENT QUALITY [✅ / ⚠️ / ❌]

### [Component Type] Configuration

**✅/❌ [EXCELLENT/GOOD/POOR] [COMPONENT] QUALITY**:

**[Sub-component 1]**:
- ✅/❌ [Feature 1]
- ✅/❌ [Feature 2]

**[Sub-component 2]**:
- ✅/❌ [Feature 1]

**✅/❌ COMPETITIVE BENCHMARK ACHIEVED**:
Per competitive_analysis.md requirements:
- ✅/❌ Matches [competitor] on [quality aspect]
- ✅/❌ Matches [competitor] on [quality aspect]

---

## 6. DOCUMENTATION QUALITY [✅ / ⚠️ / ❌]

### Release Documentation

**✅/❌ [EXCELLENT/GOOD/POOR] RELEASE IMPLEMENTATION DOCUMENT** ([filename]):
- Follows release_implementation_template.md structure ✅/❌
- Verifiable improvements with test output ✅/❌
- Complete file listing ✅/❌
- Validation commands provided ✅/❌
- In-scope vs out-of-scope clearly stated ✅/❌
- Competitive benchmark achievement documented ✅/❌
- Next steps clearly outlined ✅/❌

### Roadmap Updates

**✅/❌ ROADMAP PROPERLY UPDATED**:
- All Task [TASK_ID] checklist items marked complete ✅/❌
- Validation commands updated ✅/❌
- Quality gates documented ✅/❌
- Next task properly referenced ✅/❌

### Code Documentation

**✅/❌ [EXCELLENT/GOOD/POOR] [COMPONENT] DOCSTRINGS**:
- Every [component] has clear docstring ✅/❌
- Docstrings follow Google single-line style ✅/❌
- No ending punctuation ✅/❌
- Descriptions are behavior-focused ✅/❌

**Example**:
```python
[Example of good docstring from codebase]
```

---

## 7. VALIDATION RESULTS [✅ / ⚠️ / ❌]

### Test Execution

**✅/❌ ALL TESTS PASSING**:
```bash
[package1]: [N] passed in [X]s ✅/❌
[package2]: [N] passed in [X]s ✅/❌
Total: [N] tests ✅/❌
```

### Code Quality

**✅/❌ LINT SCRIPT PASSES**:
```bash
./scripts/lint.sh: [result] ✅/❌
```

### Coverage

**✅/❌ COVERAGE MAINTAINED/IMPROVED**:
```bash
[package1]: [X]% coverage ✅/❌
[package2]: [X]% coverage ✅/❌
```

---

## FINDINGS SUMMARY

### ✅ PASS - No Issues

**[Dimension 1]**: ✅ PASS
- [Assessment point 1]
- [Assessment point 2]

**[Dimension 2]**: ✅ PASS
- [Assessment point 1]
- [Assessment point 2]

### ⚠️ ISSUES - Minor Issues Detected

**[Issue Category]**: ⚠️ MINOR ISSUES
- [Issue description with file:line reference]
- **Recommendation**: [How to fix]
- **Impact**: [Low/Medium/High]

### ❌ BLOCKERS - Critical Issues

**[Blocker Category]**: ❌ BLOCKER
- [Issue description with file:line reference]
- **Recommendation**: [How to fix]
- **Impact**: BLOCKS COMMIT

---

## DETAILED QUALITY METRICS

### [Metric Category] Breakdown

| Category | [Metric] | Status |
|----------|---------|--------|
| [Item 1] | [Value] | ✅/❌ PASS/FAIL |
| [Item 2] | [Value] | ✅/❌ PASS/FAIL |
| **TOTAL** | **[Value]** | **✅/❌ PASS/FAIL** |

### Code Quality Metrics

| Metric | Score | Status |
|--------|-------|--------|
| [Tool 1] | [X]% | ✅/❌ PASS/FAIL |
| [Tool 2] | [X]% | ✅/❌ PASS/FAIL |
| [Metric 3] | [X]% | ✅/❌ PASS/FAIL |

### Competitive Benchmark Assessment

| Requirement | [Competitor] | [Project] | Status |
|-------------|-------------|-----------|--------|
| [Feature 1] | ✅/❌ | ✅/❌ | ✅ MATCH / ⚠️ PARTIAL / ❌ MISSING |
| [Feature 2] | ✅/❌ | ✅/❌ | ✅ MATCH / ⚠️ PARTIAL / ❌ MISSING |

**Result**: [Project] [meets/exceeds/falls short of] [competitor] quality standards

---

## RECOMMENDATIONS

### ✅ APPROVED FOR COMMIT

**[No changes required / Changes required before commit]**

### Strengths to Highlight

1. **[Strength 1]** - [Description]
2. **[Strength 2]** - [Description]
3. **[Strength 3]** - [Description]

### Required Changes (Before Commit)

1. **[Change 1]** - [Description with file:line reference]
   - Priority: [HIGH/MEDIUM/LOW]
   - Rationale: [Why this is needed]

### Future Considerations (Post-MVP)

These are NOT issues with current implementation, but potential future enhancements:

1. **[Enhancement 1]** - [Description] ([version]+)
2. **[Enhancement 2]** - [Description] ([version]+)

---

## CONCLUSION

**TASK [TASK_ID]: [✅ APPROVED - EXCELLENT QUALITY / ⚠️ APPROVED WITH ISSUES / ❌ REJECTED - NEEDS REVISION / 🚫 BLOCKED]**

[2-3 paragraph summary of implementation quality, highlighting key achievements, any issues found, and overall assessment]

**The implementation is [ready for commit without changes / ready for commit after addressing issues / not ready for commit].**

**Recommended Next Steps**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

---

**Review Completed**: [YYYY-MM-DD]  
**Review Status**: [✅ APPROVED / ⚠️ APPROVED WITH ISSUES / ❌ REJECTED / 🚫 BLOCKED]  
**Reviewer**: [REVIEWER_NAME]

---

## TEMPLATE USAGE NOTES

**This template should be used for:**
- Post-implementation quality reviews of roadmap tasks
- Comprehensive assessment before commit/merge
- Documentation of review findings and recommendations

**Companion document**: This review document should reference a corresponding implementation document (`release-v[VERSION]-implementation.md`) created using the [release implementation template](./release_implementation_template.md).

**Filename format**: Save as `release-v[VERSION]-review.md` in `docs/releases/`
- Example: `release-v0.53.3-review.md`
- Companion: `release-v0.53.3-implementation.md`

**How to use this template:**
1. Replace all `[PLACEHOLDERS]` with actual values
2. Remove sections that are not applicable to the specific task
3. Add task-specific sections as needed (e.g., "Template Content Quality" for template tasks)
4. Provide specific, actionable feedback with file:line references
5. Include actual command output, not just descriptions
6. Use ✅/❌/⚠️ status indicators consistently
7. Be thorough but concise - highlight what matters

**Status Indicators:**
- ✅ PASS - No issues detected
- ⚠️ MINOR ISSUES - Issues present but not blocking
- ❌ FAIL - Significant issues requiring changes
- 🚫 BLOCKED - Critical issues preventing progress

**Review Levels:**
- **APPROVED - EXCELLENT QUALITY**: Zero issues, exemplary implementation
- **APPROVED WITH MINOR ISSUES**: Minor issues noted but not blocking commit
- **REJECTED - NEEDS REVISION**: Significant issues require fixes before commit
- **BLOCKED**: Critical blockers prevent any progress

**Remember:**
- Review against documented standards, not personal preferences
- Provide specific file:line references for all issues
- Give concrete, actionable recommendations
- Distinguish between blockers, issues, and suggestions
- Include actual test output and validation results

**Related Documentation:**
- [Release Implementation Template](./release_implementation_template.md) - Template for implementation documentation
- [Roadmap Task Review Prompt](.github/prompts/roadmap-task-review.prompt.md) - Automated review prompt
- [Review Guidelines](../contrib/review.md) - Quality control stage documentation
