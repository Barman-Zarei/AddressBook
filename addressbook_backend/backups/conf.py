import re
from datetime import datetime, timezone

from django.conf import settings

DEFAULTS = {
    "STORAGE": "local",                 # "local" or "s3"
    "LOCAL_DIR": str(settings.BASE_DIR / "backups_data"),

    # --- automatic backups ---
    "INTERVAL_MINUTES": 30,
    # Retention (30-minute backups pile up fast): keep EVERYTHING from the last
    # KEEP_RECENT_HOURS, then only the newest backup of each day for KEEP_DAILY_DAYS.
    "KEEP_RECENT_HOURS": 48,
    "KEEP_DAILY_DAYS": 35,
    "KEEP_PRERESTORE": 5,               # safety copies made right before a restore
    # Never store a backup of a database that has no users: it is almost certainly a
    # brand-new/empty database and must not push real backups out of the retention window.
    "ALLOW_EMPTY_BACKUP": False,

    # --- automatic monthly restore (opt-in, destructive) ---
    "RESTORE_ENABLED": False,
    "RESTORE_DAY": 27,                  # day of the month (31 -> last day of shorter months)
    "RESTORE_HOUR": 12,                 # project TIME_ZONE (Asia/Tehran)
    "RESTORE_MINUTE": 0,
    "RESTORE_RUN_MIGRATE": True,        # create the tables first (needed for a brand-new DB)

    # Models that make up the data set (parents first). Add new apps' models here.
    "MODELS": ["auth.Group", "auth.User", "contacts.Contact"],

    # Secret for POST /api/internal/backup-tick/ (external cron instead of a worker).
    # Empty or shorter than 32 characters = endpoint disabled.
    "CRON_TOKEN": "",

    "S3_BUCKET": "",
    "S3_PREFIX": "addressbook-backups/",
    "S3_ENDPOINT_URL": "",              # for Cloudflare R2 / Backblaze B2 / MinIO
}


def get_config():
    cfg = dict(DEFAULTS)
    cfg.update(getattr(settings, "BACKUP", None) or {})
    return cfg


NAME_RE = re.compile(r"^(?P<kind>addressbook|prerestore)-(?P<ts>\d{8}T\d{6}Z)\.json\.gz$")
TS_FORMAT = "%Y%m%dT%H%M%SZ"


def make_name(kind, when):
    return f"{kind}-{when.astimezone(timezone.utc).strftime(TS_FORMAT)}.json.gz"


def parse_name(name):
    m = NAME_RE.match(name)
    if not m:
        return None
    when = datetime.strptime(m.group("ts"), TS_FORMAT).replace(tzinfo=timezone.utc)
    return m.group("kind"), when
