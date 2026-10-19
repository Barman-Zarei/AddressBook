from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from backups import service
from backups.storage import get_storage


def parse_moment(text):
    """'2026-10-01' -> end of that day; '2026-10-01 14:30' -> that exact minute (project time zone)."""
    for fmt, end_of_day in (("%Y-%m-%d %H:%M", False), ("%Y-%m-%dT%H:%M", False), ("%Y-%m-%d", True)):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return timezone.make_aware(dt)
    raise CommandError("Date must look like 2026-10-01 or '2026-10-01 14:30'.")


class Command(BaseCommand):
    help = "Restore the database to its state at a given date (uses the newest backup at/before it)."

    def add_arguments(self, parser):
        g = parser.add_mutually_exclusive_group()
        g.add_argument("--date", help="e.g. 2026-10-01 or '2026-10-01 14:30' (project time zone)")
        g.add_argument("--file", help="exact backup name, e.g. addressbook-20261001T060000Z.json.gz")
        g.add_argument("--list", action="store_true", help="list available backups and exit")
        parser.add_argument("--dry-run", action="store_true", help="only show which backup would be used")
        parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
        parser.add_argument("--no-safety-backup", action="store_true")

    def handle(self, *args, **o):
        storage = get_storage()
        items = service.regular_backups(storage)
        tz = timezone.get_current_timezone()

        if o["list"]:
            for i in items:
                self.stdout.write(f"{i.name}  {i.created_at.astimezone(tz):%Y-%m-%d %H:%M %Z}  {i.size} bytes")
            if not items:
                self.stdout.write("No backups found.")
            return

        if o["file"]:
            info = next((i for i in items if i.name == o["file"]), None)
            if not info:
                raise CommandError("No such backup. Use --list.")
        elif o["date"]:
            moment = parse_moment(o["date"])
            info = service.find_backup_at(storage, moment)
            if not info:
                raise CommandError("No backup exists at or before that date. Use --list.")
        else:
            raise CommandError("Give --date, --file or --list.")

        when = info.created_at.astimezone(tz)
        self.stdout.write(f"Selected backup: {info.name} (taken {when:%Y-%m-%d %H:%M %Z})")
        if o["dry_run"]:
            return
        db = settings.DATABASES["default"]
        if not o["yes"]:
            self.stdout.write(self.style.WARNING(
                f"This REPLACES all users and contacts in {db.get('NAME')}@{db.get('HOST') or 'local'} "
                "with the backup's content."))
            if input("Type 'restore' to continue: ").strip() != "restore":
                raise CommandError("Aborted.")
        service.restore_backup(info, storage, safety_backup=not o["no_safety_backup"])
        self.stdout.write(self.style.SUCCESS(f"Database restored from {info.name}."))
