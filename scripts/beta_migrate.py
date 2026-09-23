"""Thin maintainer-only wrapper for the fresh-first beta migration workflow"""

from __future__ import annotations

from quickscale_devtools.beta_migration import main

if __name__ == "__main__":
    raise SystemExit(main())
