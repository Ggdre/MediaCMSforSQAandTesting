"""
Pytest configuration and shared fixtures.

- require_postgresql: skip test when DB is not PostgreSQL (e.g. search tests).
- Ensures fixtures/test_image.png and fixtures/test_image2.jpg exist (minimal placeholder if missing).
"""

import os

import pytest

import os

import pytest


# Smallest valid 1x1 PNG (68 bytes) so tests that need an image file can run without real fixtures
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _ensure_fixture(path, content=_MINIMAL_PNG):
    """Create a minimal fixture file if it does not exist."""
    if os.path.isfile(path):
        return
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def pytest_configure(config):
    """Ensure fixture image files exist so tests do not fail with FileNotFoundError."""
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fixtures = os.path.join(root, "fixtures")
        _ensure_fixture(os.path.join(fixtures, "test_image.png"))
        _ensure_fixture(os.path.join(fixtures, "test_image2.jpg"), _MINIMAL_PNG)
    except Exception:
        pass


def _db_vendor():
    from django.db import connection
    return getattr(connection, "vendor", "unknown")


def require_postgresql(f):
    """Decorator: skip test when database is not PostgreSQL (e.g. full-text search tests)."""
    def wrapped(*args, **kwargs):
        if _db_vendor() != "postgresql":
            pytest.skip("Requires PostgreSQL (full-text search)")
        return f(*args, **kwargs)
    return wrapped
