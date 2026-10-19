import json
import logging
import re
import time
from urllib.parse import parse_qs

from django.core.cache import caches
from django.http import JsonResponse

from .conf import get_config
from .limiter import PenaltyBox, SlidingWindowLimiter
from .utils import get_client_ip, hash_value, ip_bucket, ip_in_list

logger = logging.getLogger(__name__)

_MAX_BODY_SNIFF = 4096


class Decision:
    def __init__(self, allowed=True, status=429, code="rate_limited", detail="", retry_after=0, hit=None):
        self.allowed = allowed
        self.status = status
        self.code = code
        self.detail = detail
        self.retry_after = retry_after
        self.hit = hit  # most restrictive Hit, used for response headers


class RateLimitMiddleware:
    """Put it FIRST in MIDDLEWARE so abusive traffic is rejected before any real work."""

    def __init__(self, get_response, clock=time.time):
        self.get_response = get_response
        self.clock = clock

    def __call__(self, request):
        cfg = get_config()
        if not cfg["ENABLED"] or not request.path.startswith(tuple(cfg["PATH_PREFIXES"])):
            return self.get_response(request)

        try:
            decision = self._evaluate(request, cfg)
        except Exception:
            logger.exception("rate-limit backend failure")
            if cfg["FAIL_OPEN"]:
                decision = None
            else:
                decision = Decision(False, 503, "rate_limiter_unavailable",
                                    "Service temporarily unavailable.", 5)

        if decision is not None and not decision.allowed:
            return self._reject(decision)

        response = self.get_response(request)
        if decision is not None and decision.hit is not None:
            self._headers(response, decision.hit)
        return response

    # ------------------------------------------------------------------ core
    def _evaluate(self, request, cfg):
        ip = get_client_ip(request, cfg["TRUSTED_PROXY_COUNT"])
        if ip_in_list(ip, cfg["ALLOWLIST"]):
            return None
        if ip_in_list(ip, cfg["BLOCKLIST"]):
            return Decision(False, 403, "forbidden", "Access denied.")

        cache = caches["default"]
        prefix = cfg["KEY_PREFIX"]
        limiter = SlidingWindowLimiter(cache, self.clock)
        penalty = PenaltyBox(cache, prefix, cfg["PENALTY"], self.clock)

        rule = self._match_rule(request, cfg["RULES"])
        identities = {"ip": ip_bucket(ip)}
        uid = self._user_id(request)
        if uid is not None:
            identities["user"] = str(uid)
        if rule and "username" in rule["limits"]:
            name = self._username(request)
            if name:
                identities["username"] = hash_value(name.strip().lower())

        # 1) already serving a ban?
        for dim, value in identities.items():
            if dim == "username" and not (rule and "username" in rule["limits"]):
                continue
            wait = penalty.blocked_for(dim, value)
            if wait:
                return Decision(False, 429, "temporarily_blocked",
                                "Too many requests. You are temporarily blocked.", wait)

        # 2) assemble every limit this request must satisfy
        checks = []  # (scope, dim, value, limit, window, cost)
        for dim, limits in cfg["GLOBAL"].items():
            if dim in identities:
                for limit, window in limits:
                    checks.append(("global", dim, identities[dim], limit, window, 1))
        if rule:
            cost = rule.get("cost", 1)
            for dim, limits in rule["limits"].items():
                value = identities.get(dim)
                eff_dim = dim
                if value is None and dim == "user":  # anonymous -> limit by IP instead
                    eff_dim, value = "ip", identities["ip"]
                if value is None:
                    continue
                for limit, window in limits:
                    checks.append((rule["name"], eff_dim, value, limit, window, cost))

        # 3) evaluate; on the first failure roll back what this request already consumed
        done, tightest = [], None
        for scope, dim, value, limit, window, cost in checks:
            bucket = f"{prefix}:{scope}:{dim}:{value}:{window}"
            hit = limiter.hit(bucket, limit, window, cost)
            if not hit.allowed:
                for earlier in done:
                    limiter.undo(earlier)
                block = penalty.strike(dim, value)
                if block:
                    return Decision(False, 429, "temporarily_blocked",
                                    "Too many requests. You are temporarily blocked.", block, hit)
                return Decision(False, 429, "rate_limited",
                                "Too many requests. Please slow down.", hit.retry_after, hit)
            done.append(hit)
            if scope != "global" and (tightest is None or hit.remaining < tightest.remaining):
                tightest = hit
        return Decision(True, hit=tightest or (done[0] if done else None))

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _match_rule(request, rules):
        for rule in rules:
            if rule.get("methods") and request.method not in rule["methods"]:
                continue
            if re.search(rule["path"], request.path):
                return rule
        return None

    @staticmethod
    def _user_id(request):
        parts = request.META.get("HTTP_AUTHORIZATION", "").split()
        if len(parts) != 2:
            return None
        try:
            from rest_framework_simplejwt.exceptions import TokenError
            from rest_framework_simplejwt.settings import api_settings
            from rest_framework_simplejwt.tokens import AccessToken
            if parts[0] not in api_settings.AUTH_HEADER_TYPES:
                return None
            return AccessToken(parts[1])[api_settings.USER_ID_CLAIM]
        except Exception:  # invalid / expired token -> treat as anonymous
            return None

    @staticmethod
    def _username(request):
        if request.method != "POST":
            return None
        try:
            if int(request.META.get("CONTENT_LENGTH") or 0) > _MAX_BODY_SNIFF:
                return None
            raw = request.body
            if "json" in (request.content_type or ""):
                value = json.loads(raw).get("username")
            else:
                value = parse_qs(raw.decode("utf-8", "ignore")).get("username", [None])[0]
            return value if isinstance(value, str) and value.strip() else None
        except Exception:
            return None

    @staticmethod
    def _headers(response, hit):
        response["X-RateLimit-Limit"] = str(hit.limit)
        response["X-RateLimit-Remaining"] = str(hit.remaining)
        response["X-RateLimit-Reset"] = str(hit.reset)

    def _reject(self, d):
        body = {"detail": d.detail, "code": d.code}
        if d.retry_after:
            body["retry_after"] = d.retry_after
        response = JsonResponse(body, status=d.status)
        if d.retry_after:
            response["Retry-After"] = str(d.retry_after)
        if d.hit is not None:
            self._headers(response, d.hit)
            response["X-RateLimit-Remaining"] = "0"
        return response
