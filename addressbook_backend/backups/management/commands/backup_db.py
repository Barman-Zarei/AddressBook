from django.core.management.base import BaseCommand

from backups import service
from backups.storage import get_storage


class Command(BaseCommand):
    help = "Create a database backup. With --if-due, only when the last one is older than the interval."

    def add_arguments(self, parser):
        parser.add_argument("--if-due", action="store_true",
                            help="skip if the newest backup is younger than BACKUP_INTERVAL_MINUTES "
                                 "(use from a cron job running every 30 minutes)")
        parser.add_argument("--interval-minutes", type=float, default=None)

    def handle(self, *args, **o):
        storage = get_storage()
        try:
            if o["if_due"]:
                info = service.run_if_due(storage, o["interval_minutes"])
                if info is None:
                    self.stdout.write("Not due yet - nothing to do.")
                    return
            else:
                info = service.create_backup(storage)
        except service.EmptyDatabaseError as exc:
            self.stdout.write(self.style.WARNING(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(f"Backup created: {info.name} ({info.size} bytes)"))
