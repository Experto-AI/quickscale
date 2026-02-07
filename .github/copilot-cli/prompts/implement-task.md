# Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages

Workflow: `implement-task`

## Steps

1. Stage 1: PLAN
2. Stage 2: CODE
3. Stage 3: REVIEW
4. Stage 4: TEST
5. Stage 5: COMPLETE

Arguments: `task_id`

Source: `.agent/workflows/implement-task.md`

Validation:
```bash
./scripts/lint.sh
./scripts/test_unit.sh
```
