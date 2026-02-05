---
mode: Adaptive
---
Purpose
-------
This prompt instructs the assistant to produce a single, high-quality release commit message for a new release. The assistant must locate and read the corresponding release notes and roadmap entry for the version, gather the list of commits since the previous tag, inspect the files staged for commit, and synthesize those inputs into a concise, meaningful commit title and a short, useful commit body.

This prompt operates in the REVIEW stage - use `docs/contrib/review.md` for quality control guidelines before finalizing the release.

Behavior contract (inputs / outputs / success criteria)
-----------------------------------------------------
- Inputs: optional release version string (e.g. `0.52.0`). If no version is provided, ask the user for it.
- The repository workspace (access to files under `docs/releases`, `docs/technical/roadmap.md`, and git metadata: tags, recent commits, and staged file list).
- Outputs: a single commit message consisting of a one-line title and an optional body. Title should be concise (<= 72 chars, preferably <= 50), imperative mood when appropriate, and include the version identifier. The body should be 1-10 short paragraphs/bulleted points summarizing the most important changes, linking to release notes / docs, and calling out breaking changes or migrations.

Success criteria:
- A clear one-line commit title that includes the release version and a short summary (e.g. `chore(release): v0.52.0 — faster scaffolding and critical bugfixes`).
- A commit body that references the release notes file and roadmap entry when available, summarizes the key changes (features, fixes, breaking changes), and lists notable commits (1-5 most important commit lines) or the commit count since last tag.
- The message should mention staged files that are being released (if relevant).

Required actions (what the assistant must do)
-------------------------------------------
1. If the user did not provide a release version, ask a concise clarifying question: "Which version should I create the release commit for?" and wait for input.
2. Locate the release notes file matching the version under `docs/releases/` (common names: `release-v{version}.md`, `v{version}.md`, or `release-{version}.md`). If found, read it and extract the short summary and key bullets.
3. If no direct release note exists, scan `docs/releases/` for an entry that mentions the version, and consult `docs/technical/roadmap.md` (or `docs/technical/roadmap*`) for any release-related notes for that version.
4. Determine the previous release tag by reading the latest git tag reachable from HEAD (e.g. `git describe --tags --abbrev=0` or equivalent). Gather a list of commits since that tag: include commit hash prefix, subject line, and author for the most important ones. Prefer the 3–8 most impactful commits.
5. List files currently staged for commit in the index (e.g. `git diff --name-only --staged`). Summarize if there are docs-only changes, code changes, or packaging changes.
6. Synthesize all gathered information into a commit message with:
   - Title: one line, imperative and concise, includes `v{version}`.
   - Body: short summary paragraph, 3–8 bullets of notable changes (features, fixes, breaking changes), link or path to the release notes, and a short listing of the most notable commits (hash + subject + author). If there are migration steps or breaking changes, list them clearly and first.
7. If the staged files do not match the release notes or the commits (e.g., staged files are empty), warn the user and offer to continue or abort.

8. After composing the commit message and verifying the release notes file exists (e.g. `docs/releases/release-v{version}.md`), update the roadmap entry for that version at `docs/technical/roadmap.md`:
  - Remove or collapse the detailed task/sprint checklists related to the released version.
  - Replace the removed section with a concise single-line pointer such as `Release v{version}:` (optionally followed by a one-line summary or link to the release notes).
  - If the roadmap entry cannot be found, warn the user and offer a suggested one-line replacement to insert manually.
  - Do not modify unrelated roadmap sections; commit only the minimal roadmap cleanup change alongside the release commit if the user confirms.

Formatting and stylistic constraints
----------------------------------
- Title: 50 characters preferred, never exceed 72 characters. Example formats to prefer:
- Title: 50 characters preferred, never exceed 72 characters. Example formats to prefer:
  - `v{version} feat: short summary`
  - `v{version} chore: short summary`
- Body: wrap at ~72 characters, keep paragraphs short. Use bullets for lists. Use present/imperative tense in the title and short past/present summary in body.
- Avoid verbose prose. Prioritize clarity: what changed and why it matters.

Information sources and fallback order
-------------------------------------
1. `docs/releases/release-v{version}.md` (or similarly named file in `docs/releases/`).
2. `docs/releases/` index files and `docs/technical/roadmap.md` for roadmap entries referencing the version.
3. Git metadata: latest tag, `git log` between last tag and HEAD for commit summaries.
4. Staged files (git index) to ensure the commit contents match the intended release.

Suggested git commands the assistant can rely on (implementing system should run these and provide outputs):
- Get last tag: `git describe --tags --abbrev=0`
- Commits since last tag: `git log --pretty=format:'%h %s (%an)' <last_tag>..HEAD --no-merges`
- Staged files: `git diff --name-only --staged`

Output template
---------------
Title (one line)

Body (optional, recommended)
- Short 1–2 sentence summary.
- Bullet list of notable changes (features, fixes, breaking changes).
- "Release notes: docs/releases/<file>" (or URL if available).
 - "Release notes: docs/releases/<file>" (or URL if available).

Examples
--------
Example 1 (simple):

Title:
v0.52.0 feat: faster scaffolding and critical bugfixes

Body:
Release v0.52.0 — speeds up project scaffolding and fixes a critical template rendering bug.

- Added parallelized template rendering to reduce setup time (~30% faster).
- Fixed crash when project name contained spaces (fixes #345).
- Updated docs: `docs/releases/release-v0.52.0.md`.

Release notes: docs/releases/release-v0.52.0.md
...

Example 2 (breaking changes):

Title:
v1.0.0 feat: initial stable release (breaking changes)

Body:
Release v1.0.0 — initial stable release.

- BREAKING: Removed legacy config `quickscale.conf`. See migration steps below.
- Added stable CLI commands and improved extension API.

Migration steps:
1. Backup and convert your `quickscale.conf` using `quickscale migrate-config`.

Release notes: docs/releases/release-v1.0.0.md
...

Behavior on missing/ambiguous data
----------------------------------
- If no release note or roadmap entry can be found for the specified version, clearly state that and use the commit log + staged files to synthesize a reasonable summary. Suggest creating a release notes file and include a short draft summary to paste into it.
- If there are zero staged files, warn the user: "No files are staged for commit — do you want me to create the release commit message anyway?" and pause for confirmation.

Final user prompt
-----------------
When ready to produce the commit message, present it wrapped in triple backticks and labeled as "Commit message". Ask for confirmation to run `git commit -m "<title>" -m "<body>"` (or to copy the message to clipboard) before taking any git action.
