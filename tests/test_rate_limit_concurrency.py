"""Concurrency regression for the blog API rate limiter.

The reported failure cell is production without ``REDIS_URL``: the generated
settings then select Django's database cache, whose ``incr`` is a
read-modify-write, so concurrent requests read the same counter value and
write back the same increment.  The limiter now counts in its own table with
a single atomic upsert, so this regression runs with ``DatabaseCache``
configured — the cell that used to break — drives the limiter from many
threads, and asserts the observed number of admitted requests never exceeds
the configured limit.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.test import RequestFactory, override_settings

import quickscale_modules_blog.views as blog_views

DATABASE_CACHE_BACKEND = "django.core.cache.backends.db.DatabaseCache"
DATABASE_CACHE_SETTINGS = {
    "default": {
        "BACKEND": DATABASE_CACHE_BACKEND,
        "LOCATION": "blog_throttle_regression_cache",
    }
}

#: One fixed instant so every thread lands in the same limiter window.
FIXED_NOW = 1_700_000_000
ALLOWED_REQUESTS = 5
CONCURRENT_REQUESTS = 16


@pytest.mark.django_db(transaction=True)
def test_blog_api_rate_limit_holds_under_concurrent_database_cache_requests(
    monkeypatch,
    settings,
) -> None:
    """A concurrent burst never admits more than the configured limit."""
    settings.BLOG_API_RATE_LIMIT = f"{ALLOWED_REQUESTS}/day"
    monkeypatch.setattr(blog_views, "time", lambda: FIXED_NOW)

    with override_settings(CACHES=DATABASE_CACHE_SETTINGS):
        assert settings.CACHES["default"]["BACKEND"] == DATABASE_CACHE_BACKEND
        call_command("createcachetable", verbosity=0)

        barrier = threading.Barrier(CONCURRENT_REQUESTS, timeout=30)

        def _attempt(_: int) -> bool:
            close_old_connections()
            request = RequestFactory().post(
                "/blog/api/publish/",
                REMOTE_ADDR="10.0.0.7",
            )
            barrier.wait()
            response = blog_views._enforce_blog_api_rate_limit(request)
            close_old_connections()
            return response is None

        with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
            admitted = list(pool.map(_attempt, range(CONCURRENT_REQUESTS)))

    assert admitted.count(True) == ALLOWED_REQUESTS
    assert admitted.count(False) == CONCURRENT_REQUESTS - ALLOWED_REQUESTS
