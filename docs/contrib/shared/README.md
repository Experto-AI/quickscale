# Shared Rule Sources

This directory contains the authoritative QuickScale implementation rules.

These documents are workflow-agnostic and normative. They define the
engineering constraints, quality expectations, and repository boundaries that
apply regardless of whether the work is performed by a human contributor, an AI
assistant, or a multi-agent workflow.

Shared rule documents should contain:
- principles, constraints, and prohibitions
- architecture and boundary rules
- quality expectations that hold across stages
- references to repository SSOT documents

Shared rule documents should not contain:
- required execution order or workflow sequencing
- planning, implementation, review, testing, or debugging walkthroughs
- applied checklists, repo command recipes, or AI/LLM operating guidance
- illustrative examples that are better owned by the stage guides

If a guide in `docs/contrib/` conflicts with a document in this directory, the
document in `shared/` wins on normative rules. Stage guides own applied
checklists, examples, repo commands, and stage-specific execution help.

## Authority Map

| Topic | Authoritative source | Typically applied from |
|---|---|---|
| Core design principles | [Code Principles](code_principles.md) | plan, code, review, debug |
| Code style and local conventions | [Code Style Standards](code_style_standards.md) | code, review |
| Architecture and stack boundaries | [Architecture Guidelines](architecture_guidelines.md) | plan, code, review, debug |
| Testing standards | [Testing Standards](testing_standards.md) | plan, testing, review, debug |
| Scope discipline | [Task Focus Guidelines](task_focus_guidelines.md) | plan, code, review, debug |
| Documentation conventions | [Documentation Standards](documentation_standards.md) | plan, code, review |
| Debugging and bug-fix discipline | [Debugging Standards](debugging_standards.md) | debug, review, testing |

## Use of Stage Guides

The stage guides in `docs/contrib/plan.md`, `code.md`, `review.md`,
`testing.md`, and `debug.md` are application guides only.

They help contributors apply the shared rules in a specific situation. They own
applied checklists, examples, repo commands, and AI-assistant task guidance for
that stage, but they do not define new normative rules and they do not
prescribe execution order.
