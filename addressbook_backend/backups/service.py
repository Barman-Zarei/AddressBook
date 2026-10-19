"""Backup / restore logic (logical dump through Django's serializers).

Why ``dumpdata`` instead of ``pg_dump``: Render's Python runtime doesn't ship the
PostgreSQL client tools, and for this data set (users + contacts) a JSON dump is small,
portable between databases and restores through the same models/validation as the app.
"""

import calendar
import gzip
import json
import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone as dj_timezone

from .conf import get_config, make_name
from .storage import get_storage

logger = logging.getLogger(__name__)

STATE_FILE = "scheduled-restore-state.json"
RETRY_AFTER = timedelta(minutes=10)
MAX_ATTEMPTS = 3


class BackupError(Exception):
    pass


class EmptyDatabaseError(BackupError):
    """The database has no users, so a backup of it is refused (see ALLOW_EMPTY_BACKUP)."""


def _utcnow():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ backups
def create_backup(storage=None, kind="addressbook", now=None, allow_empty=None):
    """Dump the configured models, verify the file, upload it, apply retention."""
    cfg = get_config()
    storage = storage or get_storage()
    now = now or _utcnow()
    if allow_empty is None:
        allow_empty = cfg["ALLOW_EMPTY_BACKUP"] or kind != "addressbook"
    name = make_name(kind, now)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        call_command(
            "dumpdata", *cfg["MODELS"],
            use_natural_foreign_keys=True,   # permissions referenced by codename, not id
            output=str(path), verbosity=0,
        )
        with gzip.open(path, "rt", encoding="utf-8") as fh:  # integrity check
            data = json.load(fh)
        if not isinstance(data, list):
            raise BackupError("Backup verification failed: unexpected content.")
        if not allow_empty and not any(o.get("model") == "auth.user" for o in data):
            raise EmptyDatabaseError("Database has no users - backup skipped.")
        storage.save(name, path)
        size = path.stat().st_size
    logger.info("backup created: %s (%s objects, %s bytes)", name, len(data), size)
    _apply_retention(storage, cfg, now)
    return next(i for i in storage.list() if i.name == name)


def _apply_retention(storage, cfg, now):
    tz = dj_timezone.get_current_timezone()
    items = storage.list()  # oldest first
    regular = [i for i in items if i.kind == "addressbook"]
    recent_cutoff = now - timedelta(hours=cfg["KEEP_RECENT_HOURS"])
    daily_cutoff = now - timedelta(days=cfg["KEEP_DAILY_DAYS"])

    keep, newest_of_day = set(), {}
    for i in regular:
        if i.created_at >= recent_cutoff:
            keep.add(i.name)
        elif i.created_at >= daily_cutoff:
            newest_of_day[i.created_at.astimezone(tz).date()] = i.name  # later wins
    keep.update(newest_of_day.values())
    for i in regular:
        if i.name not in keep:
            storage.delete(i.name)
            logger.info("backup pruned: %s", i.name)

    safety = [i for i in items if i.kind == "prerestore"]
    keep_n = cfg["KEEP_PRERESTORE"]
    for old in safety[:-keep_n] if keep_n > 0 else safety:
        storage.delete(old.name)


def regular_backups(storage):
    return [i for i in storage.list() if i.kind == "addressbook"]


def is_due(storage, interval_minutes=None, now=None, tolerance_seconds=30):
    """True when the newest regular backup is older than the interval (or none exists)."""
    interval_minutes = interval_minutes or get_config()["INTERVAL_MINUTES"]
    now = now or _utcnow()
    items = regular_backups(storage)
    if not items:
        return True
    age = now - items[-1].created_at
    return age >= timedelta(minutes=interval_minutes) - timedelta(seconds=tolerance_seconds)


def run_if_due(storage=None, interval_minutes=None, now=None):
    storage = storage or get_storage()
    if is_due(storage, interval_minutes, now):
        return create_backup(storage, now=now)
    return None


# ------------------------------------------------------------------ restore
def find_backup_at(storage, moment):
    """Newest regular backup taken at or before ``moment`` (aware datetime)."""
    candidates = [i for i in regular_backups(storage) if i.created_at <= moment]
    return candidates[-1] if candidates else None


def restore_backup(info, storage=None, safety_backup=True):
    """Replace the current data with the content of ``info``.

    Runs in ONE transaction: if loading fails halfway, the database stays untouched.
    A ``prerestore-*`` copy of the current state is stored first (outside the transaction).
    """
    cfg = get_config()
    storage = storage or get_storage()
    if safety_backup:
        create_backup(storage, kind="prerestore")
    models = [apps.get_model(label) for label in cfg["MODELS"]]
    with tempfile.TemporaryDirectory() as tmp:
        path = storage.fetch(info.name, tmp)
        with transaction.atomic():
            for model in reversed(models):  # children first
                model.objects.all().delete()
            call_command("loaddata", str(path), verbosity=0)
    logger.warning("database restored from %s", info.name)


# ------------------------------------------------- monthly scheduled restore
def _period(dt):
    return f"{dt.year}-{dt.month:02d}"


def _previous_period(dt):
    y, m = (dt.year, dt.month - 1) if dt.month > 1 else (dt.year - 1, 12)
    return f"{y}-{m:02d}"


def due_moment(now, cfg):
    """This month's restore moment (clamped to the month length) in project time."""
    local = now.astimezone(dj_timezone.get_current_timezone())
    day = min(cfg["RESTORE_DAY"], calendar.monthrange(local.year, local.month)[1])
    return local.replace(day=day, hour=cfg["RESTORE_HOUR"], minute=cfg["RESTORE_MINUTE"],
                         second=0, microsecond=0)


def _read_state(storage):
    raw = storage.read_text(STATE_FILE)
    return json.loads(raw) if raw else None


def _write_state(storage, **state):
    storage.write_text(STATE_FILE, json.dumps(state, indent=2))


def run_scheduled_restore(storage=None, now=None):
    """Called every minute by ``backup_scheduler``. Once a month, at the configured
    day/time, loads the newest backup into the database. Returns the BackupInfo used,
    or None when nothing happened.

    Safety rules:
    * The first time it ever runs it only *arms* the schedule - it never restores
      immediately because the date of the current month already passed.
    * The "done this month" marker lives in the backup storage, not in the database,
      because the database may be a brand-new one.
    * If the database still has users, a fresh backup is taken first, so the restore
      loses nothing. If it is empty (new DB), nothing is backed up - an empty backup
      must never become "the newest".
    * Failures are retried (3 times, 10 minutes apart) and then left for a human.
    """
    cfg = get_config()
    if not cfg["RESTORE_ENABLED"]:
        return None
    storage = storage or get_storage()
    now = now or _utcnow()
    local = now.astimezone(dj_timezone.get_current_timezone())
    period, due = _period(local), due_moment(now, cfg)

    state = _read_state(storage)
    if state is None:  # arm the schedule
        armed = period if local >= due else _previous_period(local)
        _write_state(storage, period=armed, status="armed", at=now.isoformat())
        logger.info("scheduled restore armed; next run %s", due.isoformat())
        return None
    if state.get("period") == period and state.get("status") in ("restored", "armed", "skipped-no-backup"):
        return None
    if local < due:
        return None
    if state.get("period") == period and state.get("status") == "failed":
        last = datetime.fromisoformat(state["at"])
        if state.get("attempts", 0) >= MAX_ATTEMPTS or now - last < RETRY_AFTER:
            return None
    attempts = state.get("attempts", 0) if state.get("period") == period else 0

    try:
        if cfg["RESTORE_RUN_MIGRATE"]:
            call_command("migrate", interactive=False, verbosity=0)
        if get_user_model().objects.exists():
            create_backup(storage, now=now)  # capture the newest data before replacing it
        latest = find_backup_at(storage, now)
        if latest is None:
            _write_state(storage, period=period, status="skipped-no-backup", at=now.isoformat())
            logger.error("scheduled restore skipped: no backup available")
            return None
        restore_backup(latest, storage)
    except Exception as exc:
        _write_state(storage, period=period, status="failed", attempts=attempts + 1,
                     error=repr(exc), at=now.isoformat())
        logger.exception("scheduled restore failed (attempt %s)", attempts + 1)
        raise
    _write_state(storage, period=period, status="restored", backup=latest.name, at=now.isoformat())
    return latest


# ------------------------------------------------------------ one scheduler tick
def tick(storage=None, interval_minutes=None, now=None):
    """Everything the scheduler does in one pass: the monthly restore check, then a
    backup if one is due. Used by the ``backup_scheduler`` worker AND by the HTTP
    endpoint an external cron calls when no paid worker is available."""
    storage = storage or get_storage()
    result = {"restored": None, "backup": None, "skipped": None}
    restored = run_scheduled_restore(storage, now)
    if restored:
        result["restored"] = restored.name
    try:
        info = run_if_due(storage, interval_minutes, now)
        if info:
            result["backup"] = info.name
    except EmptyDatabaseError as exc:
        result["skipped"] = str(exc)
    return result
