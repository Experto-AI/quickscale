# Versioning (single-source)

Keep versioning simple: edit the single `VERSION` file at the repository root
and use the bundled script to sync metadata and embed a static package version.

What to do for a release (exact steps)

1) Edit VERSION
   - Open `VERSION` and set the new version (eg. 0.56.3 or 1.0.0)

2) Sync pyproject/docs and embed the static version
   - Dry-run to see changes: 
     scripts/version_tool.sh sync
   - Apply changes to `pyproject.toml` and docs:
     scripts/version_tool.sh sync --apply
   - Embed a static `_version.py` into packages (required before building):
     scripts/version_tool.sh embed
   - Or run both together:
     scripts/version_tool.sh apply

3) Commit, tag, push
   - Example:
     git add VERSION quickscale_core/pyproject.toml quickscale_cli/pyproject.toml \
       quickscale_core/src/quickscale_core/_version.py quickscale_cli/src/quickscale_cli/_version.py
     git commit -m "release: bump to $(cat VERSION)"
     git tag v$(cat VERSION)
     git push && git push --tags

4) Build & publish (example using Poetry):
   poetry build
   poetry publish

Quick checks

- Verify repository `VERSION` matches packages:
  scripts/version_tool.sh check

