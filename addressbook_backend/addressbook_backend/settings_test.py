"""Settings for running the test-suite without PostgreSQL:
    python manage.py test --settings=addressbook_backend.settings_test
"""
from .settings import *  # noqa

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
