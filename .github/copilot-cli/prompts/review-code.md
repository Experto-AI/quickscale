# Review staged code changes for quality, scope compliance, and completeness

Workflow: `review-code`

## Steps

1. Step 1: Gather Context
2. Step 2: Scope Compliance Check
3. Step 3: Architecture Review
4. Step 4: Code Quality Review
5. Step 5: Testing Review
6. Step 6: Documentation Review
7. Step 7: Validation
8. Step 8: Generate Report

Arguments: `task_id`

Source: `.agent/workflows/review-code.md`

Validation:
```bash
./scripts/lint.sh
./scripts/test_unit.sh
```
