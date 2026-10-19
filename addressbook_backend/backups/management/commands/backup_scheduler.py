import logging
import signal
import threading

from django.core.management.base import BaseCommand

from backups import service
from backups.conf import get_config
from backups.storage import get_storage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Long-running process (run it as ONE Render Background Worker):\n"
        "  * a backup every BACKUP_INTERVAL_MINUTES (default 30)\n"
        "  * if BACKUP_RESTORE_ENABLED: once a month, at BACKUP_RESTORE_DAY/TIME, load the newest "
        "backup into the database.\n"
        "All schedule state is derived from the storage, so restarts never reset it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--interval-minutes", type=float, default=None)
        parser.add_argument("--check-seconds", type=float, default=60)

    def handle(self, *args, **o):
        cfg = get_config()
        interval = o["interval_minutes"] or cfg["INTERVAL_MINUTES"]
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        self.stdout.write(
            f"Scheduler started: backup every {interval:g} min; monthly restore "
            + (f"ON (day {cfg['RESTORE_DAY']} at {cfg['RESTORE_HOUR']:02d}:{cfg['RESTORE_MINUTE']:02d})"
               if cfg["RESTORE_ENABLED"] else "OFF")
        )
        while not stop.is_set():
            try:
                result = service.tick(get_storage(), interval)
                if result["restored"]:
                    self.stdout.write(f"Monthly restore done from {result['restored']}")
                if result["backup"]:
                    self.stdout.write(f"Backup created: {result['backup']}")
                if result["skipped"]:
                    logger.warning("%s", result["skipped"])
            except Exception as exc:  # keep the loop alive; try again at the next tick
                self.stderr.write(f"Scheduler step failed: {exc!r}")
            stop.wait(o["check_seconds"])
        self.stdout.write("Scheduler stopped.")
