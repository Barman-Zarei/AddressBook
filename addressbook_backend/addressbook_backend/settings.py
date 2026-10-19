"""
Django settings for the AddressBook V7.9.0 backend.
Database: PostgreSQL (hosted on Render)
Auth: JWT (djangorestframework-simplejwt)
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")

DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",

    "accounts",
    "contacts",
    "ratelimiter",
    "backups",
]

MIDDLEWARE = [
    "ratelimiter.middleware.RateLimitMiddleware",   # first: reject abusive traffic cheaply
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "addressbook_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "addressbook_backend.wsgi.application"

# --- Database: PostgreSQL on Render ---
DB_OPTIONS = {"sslmode": os.getenv("DB_SSLMODE", "require")}
if os.getenv("DB_SSLCERT"):
    DB_OPTIONS["sslcert"] = os.getenv("DB_SSLCERT")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": DB_OPTIONS,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- REST Framework / JWT ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}


# --- Cache (rate-limit counters) ---
# With several gunicorn workers / instances the counters MUST live in a shared cache:
# set REDIS_URL (Render Key Value / Redis). Without it each worker counts on its own.
if os.getenv("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_URL"),
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Rate limiting (see ratelimiter/conf.py for every option and the default rules) ---
RATE_LIMIT = {
    "ENABLED": os.getenv("RATE_LIMIT_ENABLED", "True") == "True",
    "TRUSTED_PROXY_COUNT": int(os.getenv("RATE_LIMIT_TRUSTED_PROXIES", "1")),
    "ALLOWLIST": [x for x in os.getenv("RATE_LIMIT_ALLOWLIST", "").split(",") if x],
    "BLOCKLIST": [x for x in os.getenv("RATE_LIMIT_BLOCKLIST", "").split(",") if x],
}

# --- Database backups (see backups/conf.py) ---
def _hhmm(text):
    hour, minute = text.split(":")
    return int(hour), int(minute)


_restore_hour, _restore_minute = _hhmm(os.getenv("BACKUP_RESTORE_TIME", "12:00"))
BACKUP = {
    "STORAGE": os.getenv("BACKUP_STORAGE", "local"),
    "LOCAL_DIR": os.getenv("BACKUP_LOCAL_DIR", str(BASE_DIR / "backups_data")),
    "INTERVAL_MINUTES": float(os.getenv("BACKUP_INTERVAL_MINUTES", "30")),
    "KEEP_RECENT_HOURS": int(os.getenv("BACKUP_KEEP_RECENT_HOURS", "48")),
    "KEEP_DAILY_DAYS": int(os.getenv("BACKUP_KEEP_DAILY_DAYS", "35")),
    "RESTORE_ENABLED": os.getenv("BACKUP_RESTORE_ENABLED", "False") == "True",
    "RESTORE_DAY": int(os.getenv("BACKUP_RESTORE_DAY", "27")),
    "RESTORE_HOUR": _restore_hour,
    "RESTORE_MINUTE": _restore_minute,
    "CRON_TOKEN": os.getenv("BACKUP_CRON_TOKEN", ""),
    "S3_BUCKET": os.getenv("BACKUP_S3_BUCKET", ""),
    "S3_PREFIX": os.getenv("BACKUP_S3_PREFIX", "addressbook-backups/"),
    "S3_ENDPOINT_URL": os.getenv("BACKUP_S3_ENDPOINT_URL", ""),
}
