# Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages

Follow the implement-task workflow for QuickScale development.

## Steps

1. Stage 1: PLAN
2. Stage 2: CODE
3. Stage 3: REVIEW
4. Stage 4: TEST
5. Stage 5: COMPLETE

Target: $TASK_ID

Read the full workflow at `.agent/workflows/implement-task.md` and follow it step by step.

## Validation

Always run before completing:
```bash
./scripts/lint.sh
./scripts/test_unit.sh
```
