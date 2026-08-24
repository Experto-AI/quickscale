# Local wheelhouse resolution

QuickScale can replace the generated project's published `quickscale-core`
dependency range with an exact local wheel during development and
installed-wheel acceptance testing. The dependency synchronizer applies this
seam to both the direct project dependency update and the embedded module
`pyproject.toml` path-repair pass. Published third-party dependencies keep their
manifest-derived values; the wheelhouse is not a replacement package index.

## Wheelhouse selection

The `QUICKSCALE_LOCAL_WHEELHOUSE` environment variable is an explicit override.
When it is set, it must contain an absolute path to an existing directory; an
empty value is invalid.
For a dependency named `quickscale-core`, the synchronizer searches that
directory for exactly one wheel matching the normalized pattern
`quickscale_core-*.whl`.

When the variable is unset, an installed CLI may implicitly use
`sys.prefix/quickscale_wheels`, the wheelhouse staged by the global-install
workflow. If that implicit wheelhouse has no matching wheel, the synchronizer
keeps the published manifest version range; this preserves the normal fallback
for locally installed builds whose wheelhouse is incomplete. An unset variable
with no staged wheelhouse also keeps the manifest version range.

## Failure modes

- A non-absolute or nonexistent explicit path raises `DependencySyncError` and
  names the required environment-variable contract.
- An explicit directory with no matching `quickscale-core` wheel raises
  `DependencySyncError`.
  The error names `QUICKSCALE_LOCAL_WHEELHOUSE`, the searched directory, the
  attempted normalized glob pattern, and the wheels that were available, so an
  acceptance run cannot silently test a published artifact instead.
- More than one matching wheel raises `DependencySyncError` because the local
  artifact is ambiguous.
- With no explicit wheelhouse, no staged wheelhouse, or an unmatched implicit
  wheelhouse, the manifest version specification remains authoritative.

To use local resolution, build or copy one matching `.whl` into the explicit
directory and rerun the command. To use the published dependency range, unset
`QUICKSCALE_LOCAL_WHEELHOUSE`.
