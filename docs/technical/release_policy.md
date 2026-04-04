# Release Documentation Policy

When a QuickScale version is published, keep the release record single-source and public:

- `CHANGELOG.md` is the canonical all-version history index.
- `docs/releases/release-<version>.md` is the official release note linked from the GitHub tag and the release PR.
- `docs/technical/release_summary_template.md` is the required template for those release notes.
- `docs/technical/roadmap.md` tracks active or unreleased release-closeout work until the tagged release is cut.

This keeps release history easy to scan and avoids parallel release documents drifting out of sync.

## Required Release Documentation Conventions

- **Changelog entry**: Add or update the version entry in `CHANGELOG.md` for every completed release record.
- **Release-note filename**: `docs/releases/release-<version>.md` (for example, `release-v0.75.0.md`) for every tagged public release.
- **Release-note template**: Use `docs/technical/release_summary_template.md`.
- **Publication rule**: Only create a file in `docs/releases/` when it is the release note that will be linked from the GitHub tag and release PR.
- **Minimum content**: release focus, shipped outcomes, breaking changes or migration notes when relevant, validation summary, and deferred follow-up.
- Link back to the roadmap and to `decisions.md` where appropriate.
- Keep maintainer-only review detail in the release PR or active roadmap section rather than in a second release document.
- For internal-only or not-yet-tagged work, keep status in `docs/technical/roadmap.md` until the public release is cut.

## Release Documentation Process

Follow these steps after completing a release:

1. Update `CHANGELOG.md` with the release version, date, and concise shipped outcome.
2. When cutting the tagged release, add `docs/releases/release-<version>.md` using the release summary template.
3. Link the GitHub tag and the release PR to that `docs/releases/` file.
4. Replace the completed roadmap section with a concise pointer once the changelog entry and official release note are in place.
5. Update indexes and other documentation links if necessary.

For unreleased or internal-only versions, keep closeout notes in the roadmap until the tagged public release exists.

This policy keeps `CHANGELOG.md` as the history index, makes each published `docs/releases/` file the single public artifact, and avoids dead archive guidance.
