"""Thin maintainer-only wrapper for the fresh-first website migration workflow"""

from __future__ import annotations

from quickscale_devtools.website_migration import main

if __name__ == "__main__":
    raise SystemExit(main())
