import json
import tempfile
from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from contacts.models import Contact

from . import service
from .storage import LocalStorage


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


class Base(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = LocalStorage(self.tmp.name)

    def snapshot(self):
        return (
            sorted(User.objects.values_list("id", "username", "password")),
            sorted(Contact.objects.values_list("id", "owner_id", "name", "phone")),
        )


class BackupRestoreTests(Base):
    def test_roundtrip_restores_exact_state_including_ids_and_password_hashes(self):
        u = User.objects.create_user("ali", password="secret-123")
        Contact.objects.create(owner=u, name="Sara", phone="0912")
        before = self.snapshot()
        info = service.create_backup(self.storage, now=utc(2026, 10, 1, 6))

        Contact.objects.all().delete()
        User.objects.create_user("intruder", password="x")
        u.username = "changed"
        u.save()
        self.assertNotEqual(before, self.snapshot())

        service.restore_backup(info, self.storage)
        self.assertEqual(before, self.snapshot())
        self.assertTrue(User.objects.get(username="ali").check_password("secret-123"))

    def test_restore_creates_prerestore_safety_copy(self):
        User.objects.create_user("a", password="x")
        info = service.create_backup(self.storage, now=utc(2026, 10, 1))
        User.objects.create_user("b", password="x")
        service.restore_backup(info, self.storage)
        self.assertTrue(any(i.kind == "prerestore" for i in self.storage.list()))
        self.assertEqual(User.objects.count(), 1)

    def test_failed_restore_leaves_database_untouched(self):
        User.objects.create_user("a", password="x")
        info = service.create_backup(self.storage, now=utc(2026, 10, 1))
        (self.storage.dir / info.name).write_bytes(b"not a gzip file")
        before = self.snapshot()
        with self.assertRaises(Exception):
            service.restore_backup(info, self.storage, safety_backup=False)
        self.assertEqual(before, self.snapshot())

    def test_find_backup_at_picks_newest_not_after_date(self):
        User.objects.create_user("a", password="x")
        for day in (1, 2, 4):
            service.create_backup(self.storage, now=utc(2026, 10, day, 6))
        pick = lambda *a: service.find_backup_at(self.storage, utc(*a))
        self.assertEqual(pick(2026, 10, 3).created_at, utc(2026, 10, 2, 6))
        self.assertEqual(pick(2026, 10, 4, 6).created_at, utc(2026, 10, 4, 6))
        self.assertIsNone(pick(2026, 9, 30))


class IntervalAndGuardTests(Base):
    def setUp(self):
        super().setUp()
        User.objects.create_user("a", password="x")

    def test_is_due_follows_30_minute_interval(self):
        t0 = utc(2026, 10, 1, 0)
        self.assertTrue(service.is_due(self.storage, 30, t0))  # nothing yet
        service.create_backup(self.storage, now=t0)
        self.assertFalse(service.is_due(self.storage, 30, t0 + timedelta(minutes=29)))
        self.assertTrue(service.is_due(self.storage, 30, t0 + timedelta(minutes=30)))
        self.assertIsNone(service.run_if_due(self.storage, 30, t0 + timedelta(minutes=10)))
        self.assertIsNotNone(service.run_if_due(self.storage, 30, t0 + timedelta(minutes=31)))

    def test_prerestore_copies_do_not_reset_the_schedule(self):
        t0 = utc(2026, 10, 1)
        service.create_backup(self.storage, now=t0)
        service.create_backup(self.storage, kind="prerestore", now=t0 + timedelta(minutes=29))
        self.assertTrue(service.is_due(self.storage, 30, t0 + timedelta(minutes=30)))

    def test_empty_database_is_never_backed_up(self):
        service.create_backup(self.storage, now=utc(2026, 10, 1))
        User.objects.all().delete()
        with self.assertRaises(service.EmptyDatabaseError):
            service.create_backup(self.storage, now=utc(2026, 10, 1, 1))
        self.assertEqual(len(self.storage.list()), 1)

    @override_settings(BACKUP={"KEEP_RECENT_HOURS": 2, "KEEP_DAILY_DAYS": 3})
    def test_tiered_retention(self):
        from .conf import make_name
        base = utc(2026, 10, 10, 12)
        self.storage.dir.mkdir(parents=True, exist_ok=True)
        originals = []
        for n in range(5 * 48 + 1):  # a backup every 30 min for 5 days
            when = base - timedelta(minutes=30 * n)
            (self.storage.dir / make_name("addressbook", when)).write_bytes(b"[]")
            originals.append(when)

        service._apply_retention(self.storage, service.get_config(), base)
        kept = [i.created_at for i in self.storage.list()]
        recent = [t for t in kept if t >= base - timedelta(hours=2)]
        older = [t for t in kept if t < base - timedelta(hours=2)]
        self.assertEqual(len(recent), 5)                 # last 2 h: all of them
        self.assertTrue(older and len(older) <= 4)       # then ~1 per day, nothing before the cutoff
        self.assertTrue(all(t >= base - timedelta(days=3) for t in older))
        self.assertEqual(len({t.astimezone(service.dj_timezone.get_current_timezone()).date()
                              for t in older}), len(older))
        self.assertLess(len(kept), 15)                   # 241 files shrank to a handful


SCHEDULE = {"RESTORE_ENABLED": True, "RESTORE_DAY": 15, "RESTORE_HOUR": 3, "RESTORE_MINUTE": 0,
            "RESTORE_RUN_MIGRATE": False}


@override_settings(BACKUP=SCHEDULE)
class ScheduledRestoreTests(Base):
    # TIME_ZONE is Asia/Tehran (+03:30): 12:00 UTC on the 15th is 15:30 local, after 03:00.
    DUE = utc(2026, 10, 15, 12)
    BEFORE = utc(2026, 10, 14, 12)

    def run_sched(self, now):
        return service.run_scheduled_restore(self.storage, now)

    def test_arms_first_then_restores_on_the_date(self):
        u = User.objects.create_user("ali", password="x")
        Contact.objects.create(owner=u, name="Sara", phone="1")
        service.create_backup(self.storage, now=utc(2026, 10, 2))
        before = self.snapshot()

        self.assertIsNone(self.run_sched(utc(2026, 10, 2, 12)))  # arms, no restore
        Contact.objects.all().delete()                           # DB gets replaced by an empty one
        User.objects.all().delete()
        self.assertIsNone(self.run_sched(self.BEFORE))           # not yet
        self.assertEqual(User.objects.count(), 0)
        self.assertIsNotNone(self.run_sched(self.DUE))           # restores
        self.assertEqual(self.snapshot(), before)

    def test_live_database_loses_nothing(self):
        u = User.objects.create_user("ali", password="x")
        service.create_backup(self.storage, now=utc(2026, 10, 2))
        self.run_sched(utc(2026, 10, 3))
        Contact.objects.create(owner=u, name="NewAfterBackup", phone="9")  # not in any backup yet
        self.run_sched(self.DUE)
        self.assertTrue(Contact.objects.filter(name="NewAfterBackup").exists())

    def test_brand_new_empty_database_gets_the_backup_and_no_empty_backup_is_made(self):
        u = User.objects.create_user("ali", password="x")
        Contact.objects.create(owner=u, name="Sara", phone="1")
        service.create_backup(self.storage, now=utc(2026, 10, 14))
        self.run_sched(utc(2026, 10, 3))   # arm
        Contact.objects.all().delete()     # simulate the replaced (empty) database
        User.objects.all().delete()
        n_before = len(service.regular_backups(self.storage))
        self.run_sched(self.DUE)
        self.assertEqual(len(service.regular_backups(self.storage)), n_before)
        self.assertEqual(Contact.objects.get().name, "Sara")

    def test_runs_once_per_month_and_again_next_month(self):
        User.objects.create_user("ali", password="x")
        service.create_backup(self.storage, now=utc(2026, 10, 2))
        self.run_sched(utc(2026, 10, 3))
        self.assertIsNotNone(self.run_sched(self.DUE))
        self.assertIsNone(self.run_sched(self.DUE + timedelta(hours=5)))
        self.assertIsNone(self.run_sched(utc(2026, 10, 30)))
        self.assertIsNotNone(self.run_sched(utc(2026, 11, 15, 12)))

    def test_first_start_after_the_date_does_not_restore_immediately(self):
        User.objects.create_user("ali", password="x")
        service.create_backup(self.storage, now=utc(2026, 10, 2))
        self.assertIsNone(self.run_sched(utc(2026, 10, 20)))
        self.assertIsNone(self.run_sched(utc(2026, 10, 25)))
        self.assertIsNotNone(self.run_sched(utc(2026, 11, 15, 12)))

    @override_settings(BACKUP={**SCHEDULE, "RESTORE_DAY": 31})
    def test_day_31_is_clamped_to_month_end(self):
        User.objects.create_user("ali", password="x")
        service.create_backup(self.storage, now=utc(2026, 10, 2))
        self.run_sched(utc(2026, 10, 3))
        self.assertIsNone(self.run_sched(utc(2026, 11, 29, 12)))
        self.assertIsNotNone(self.run_sched(utc(2026, 11, 30, 12)))  # Nov has 30 days

    @override_settings(BACKUP={**SCHEDULE, "RESTORE_ENABLED": False})
    def test_disabled_does_nothing(self):
        self.assertIsNone(self.run_sched(self.DUE))
        self.assertIsNone(self.storage.read_text(service.STATE_FILE))

    def test_failure_is_retried_a_limited_number_of_times(self):
        User.objects.create_user("ali", password="x")
        info = service.create_backup(self.storage, now=utc(2026, 10, 2))
        self.run_sched(utc(2026, 10, 3))
        (self.storage.dir / info.name).write_bytes(b"broken")
        User.objects.all().delete()  # empty DB -> no fresh backup, the broken one is picked
        with self.assertRaises(Exception):
            self.run_sched(self.DUE)
        self.assertIsNone(self.run_sched(self.DUE + timedelta(minutes=2)))      # too soon
        for minutes in (11, 22):
            with self.assertRaises(Exception):
                self.run_sched(self.DUE + timedelta(minutes=minutes))
        self.assertIsNone(self.run_sched(self.DUE + timedelta(minutes=40)))     # gave up
        state = json.loads(self.storage.read_text(service.STATE_FILE))
        self.assertEqual((state["status"], state["attempts"]), ("failed", 3))


TOKEN = "t" * 40


class TickEndpointTests(Base):
    URL = "/api/internal/backup-tick/"

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
        self.cache = cache
        ctx = override_settings(BACKUP={"CRON_TOKEN": TOKEN, "LOCAL_DIR": self.tmp.name,
                                        "RESTORE_ENABLED": False})
        ctx.enable()
        self.addCleanup(ctx.disable)
        User.objects.create_user("a", password="x")

    def post(self, token=TOKEN):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
        return self.client.post(self.URL, **extra)

    def test_requires_the_right_token(self):
        self.assertEqual(self.post(None).status_code, 403)
        self.assertEqual(self.post("wrong").status_code, 403)
        self.assertEqual(self.post(TOKEN[:-1] + "x").status_code, 403)
        self.assertEqual(self.client.get(self.URL).status_code, 405)

    def test_disabled_without_a_long_enough_token(self):
        with override_settings(BACKUP={"CRON_TOKEN": "short", "LOCAL_DIR": self.tmp.name}):
            self.assertEqual(self.post("short").status_code, 404)
        with override_settings(BACKUP={"LOCAL_DIR": self.tmp.name}):
            self.assertEqual(self.post("").status_code, 404)

    def test_creates_a_backup_then_waits_until_next_is_due(self):
        first = self.post()
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["backup"].startswith("addressbook-"))
        self.assertIsNone(self.post().json()["backup"])  # not due yet
        self.assertEqual(len(self.storage.list()), 1)

    def test_overlapping_call_is_refused_and_lock_is_released(self):
        self.cache.add("backups:tick-lock", 1, 60)
        self.assertEqual(self.post().json(), {"status": "busy"})
        self.cache.delete("backups:tick-lock")
        self.assertEqual(self.post().json()["status"], "ok")
        self.assertIsNone(self.cache.get("backups:tick-lock"))

    def test_empty_database_is_skipped_not_an_error(self):
        User.objects.all().delete()
        body = self.post().json()
        self.assertEqual(body["status"], "ok")
        self.assertIsNone(body["backup"])
        self.assertIn("no users", body["skipped"])

    def test_failure_returns_500_and_releases_lock(self):
        from unittest import mock
        with mock.patch("backups.service.tick", side_effect=RuntimeError("boom")):
            self.assertEqual(self.post().status_code, 500)
        self.assertIsNone(self.cache.get("backups:tick-lock"))
