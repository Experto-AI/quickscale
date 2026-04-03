# QuickScale Release Archive

**Purpose**: `docs/releases-archive/` stores exception-only maintainer records. It is not the canonical release history and should not duplicate [CHANGELOG.md](../../CHANGELOG.md) or the public summaries in [../releases/](../releases/).

**For canonical release history**: See [CHANGELOG.md](../../CHANGELOG.md)

**For public release notes**: See [../releases/](../releases/)

**For active and upcoming scope**: See [roadmap.md](./roadmap.md)

---

## Release Record Model

1. `CHANGELOG.md` is the canonical all-version release index.
2. `docs/releases/release-vX.XX.X.md` is the default public artifact for a published release.
3. `docs/releases-archive/release-vX.XX.X-{implementation,review}.md` is optional and exception-only.
4. `roadmap.md` stays focused on active and upcoming work.

---

## When Archive Records Are Appropriate

Create an archive record only when at least one of these is true:

- the version is internal-only, unpublished, or still awaiting public closeout
- maintainers need a retrospective or handoff record with detail that would overwhelm the public summary
- a formal review artifact is required
- the work contains operational or validation detail better kept out of the reader-facing summary

---

## When Not To Use The Archive

- Do not create an implementation or review document just because a release exists.
- Do not mirror every changelog entry here.
- Do not turn this page into a second version-by-version changelog.

---

## Current Archive Categories

| Category | What lives here | Examples |
|----------|-----------------|----------|
| Legacy archive history | Historical implementation/review docs created before summaries became the default public artifact | v0.52.0-v0.73.0 implementation/review files in [../releases-archive/](../releases-archive/) |
| Active exceptions | Releases that currently rely on a maintainer archive because the public summary is absent or the record is retrospective | [v0.77.0 implementation archive](../releases-archive/release-v0.77.0-implementation.md), [v0.79.0 implementation archive](../releases-archive/release-v0.79.0-implementation.md) |
| Formal reviews | Archived quality-review documents created when maintainers want a durable review artifact | [v0.72.0 review](../releases-archive/release-v0.72.0-review.md) |

---

## Naming Convention

- `release-vX.XX.X-implementation.md` - archived maintainer implementation record
- `release-vX.XX.X-review.md` - archived maintainer review record
- `release-vX.XX.X-plan.md` - archived planning/design record when used

Store these files in [../releases-archive/](../releases-archive/).

---

## Legacy Notes

- Historical snapshots or older branches may contain review files outside `docs/releases-archive/`; preserve those placements as legacy history rather than a signal about the current tree.
- Existing files in [../releases-archive/](../releases-archive/) remain valid historical records and do not need to be rewritten just to match the current policy.
- New releases should follow the public-summary-first model unless an exception is justified.

---

**Last Updated**: 2026-04-03
**Current Active Release Tracking**: [roadmap.md](./roadmap.md)
**Default Public Release Notes**: [../releases/](../releases/)

---
