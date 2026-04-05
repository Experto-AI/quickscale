"""Thin maintainer-only wrapper for fresh-first exec and in-place flow"""

from __future__ import annotations

from quickscale_cli.beta_migration import main

if __name__ == "__main__":
    raise SystemExit(main())
