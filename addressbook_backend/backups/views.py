import hmac
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import service
from .conf import get_config

logger = logging.getLogger(__name__)

MIN_TOKEN_LENGTH = 32
LOCK_KEY = "backups:tick-lock"
LOCK_SECONDS = 300


@csrf_exempt
@require_POST
def backup_tick(request):
    """POST /api/internal/backup-tick/   header: Authorization: Bearer <BACKUP_CRON_TOKEN>

    Call it every ~10 minutes from an external cron. Each call does the same as one pass
    of ``manage.py backup_scheduler``: the monthly-restore check, then a backup if the
    last one is older than BACKUP_INTERVAL_MINUTES. Calling it more often is harmless.
    """
    expected = get_config()["CRON_TOKEN"]
    if len(expected) < MIN_TOKEN_LENGTH:  # not configured -> behave as if it doesn't exist
        return JsonResponse({"detail": "Not found."}, status=404)

    parts = request.META.get("HTTP_AUTHORIZATION", "").split()
    given = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else ""
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    # Two overlapping calls must never run a backup and a restore at the same time.
    if not cache.add(LOCK_KEY, 1, LOCK_SECONDS):
        return JsonResponse({"status": "busy"})
    try:
        result = service.tick()
    except Exception:
        logger.exception("backup tick failed")
        return JsonResponse({"status": "error"}, status=500)
    finally:
        cache.delete(LOCK_KEY)
    return JsonResponse({"status": "ok", **result})
