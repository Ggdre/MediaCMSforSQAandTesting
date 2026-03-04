# Test settings: SQLite + in-memory cache so pytest runs without PostgreSQL/Redis.
# Usage: set DJANGO_SETTINGS_MODULE=cms.test_settings then run pytest.

import os

os.environ.setdefault("TESTING", "1")

from .settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Celery runs tasks synchronously in tests (no Redis needed)
CELERY_TASK_ALWAYS_EAGER = True
BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

REDIS_LOCATION = "redis://127.0.0.1:6379/1"  # not used when cache is locmem

# Disable migrations that need PostgreSQL (e.g. SearchVector) if needed;
# for basic tests, SQLite works.
# SILENCED_SYSTEM_CHECKS = ["models.W036"]
