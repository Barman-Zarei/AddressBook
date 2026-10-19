"""Rate-limiter configuration.

Everything here can be overridden from settings.py with a ``RATE_LIMIT`` dict
(top-level keys are replaced; ``PENALTY`` is merged key by key).

A limit is a ``(max_requests, window_seconds)`` pair.  Limits are grouped by the
*dimension* they are counted against:

    ip        client address (IPv6 is collapsed to its /64)
    user      authenticated user id taken from the JWT (falls back to ``ip``)
    username  the username submitted in the request body (login/admin forms)

A request must pass **every** limit of its rule, plus the GLOBAL ones.
The first rule whose ``path`` regex (and optional ``methods``) matches is used.
"""

import copy

from django.conf import settings

DEFAULTS = {
    "ENABLED": True,
    "KEY_PREFIX": "rl",
    # Only paths starting with one of these are inspected.
    "PATH_PREFIXES": ("/api/", "/admin/"),
    # Number of reverse proxies in front of Django that append to X-Forwarded-For.
    # Render = 1. Use 0 when Django is exposed directly (then XFF is ignored).
    "TRUSTED_PROXY_COUNT": 1,
    # IPs / CIDRs that skip every check, or are rejected outright.
    "ALLOWLIST": [],
    "BLOCKLIST": [],
    # If the cache backend is down: True = let traffic through, False = answer 503.
    "FAIL_OPEN": True,
    # Escalating bans for clients that keep hitting limits.
    "PENALTY": {
        "STRIKES": 5,          # rejected requests ...
        "STRIKE_WINDOW": 600,  # ... within this many seconds trigger a block
        "BASE_BLOCK": 60,      # first block lasts this long, then doubles each time
        "MAX_BLOCK": 86400,    # never block longer than this
        "MEMORY": 86400,       # how long the "repeat offender" level is remembered
    },
    # Cheap first line of defence against floods, counted per IP for any API path.
    "GLOBAL": {
        "ip": [(120, 60), (3000, 3600)],
    },
    "RULES": [
        {
            "name": "auth-login",
            "path": r"^/api/auth/login/$",
            "methods": ["POST"],
            "limits": {
                "ip": [(10, 60), (60, 3600)],
                # Per account, across all IPs -> stops distributed password guessing.
                "username": [(5, 300), (20, 3600)],
            },
        },
        {
            "name": "auth-register",
            "path": r"^/api/auth/register/$",
            "methods": ["POST"],
            "limits": {"ip": [(3, 3600), (10, 86400)]},
        },
        {
            "name": "auth-refresh",
            "path": r"^/api/auth/refresh/$",
            "limits": {"ip": [(30, 60)]},
        },
        {
            "name": "auth-delete",
            "path": r"^/api/auth/delete/$",
            "limits": {"user": [(3, 3600)]},
        },
        {
            "name": "internal-tick",
            "path": r"^/api/internal/",
            "limits": {"ip": [(20, 60), (200, 3600)]},
        },
        {
            "name": "contacts-search",
            "path": r"^/api/contacts/search/$",
            "limits": {"user": [(30, 60), (600, 3600)]},
            "cost": 2,  # a search is heavier than a plain read
        },
        {
            "name": "contacts-write",
            "path": r"^/api/contacts/",
            "methods": ["POST", "PUT", "PATCH", "DELETE"],
            "limits": {"user": [(30, 60), (500, 3600)]},
        },
        {
            "name": "contacts-read",
            "path": r"^/api/contacts/",
            "limits": {"user": [(120, 60), (3000, 3600)]},
        },
        {
            "name": "admin-login",
            "path": r"^/admin/",
            "methods": ["POST"],
            "limits": {"ip": [(5, 300)], "username": [(5, 300)]},
        },
    ],
}


def get_config():
    cfg = copy.deepcopy(DEFAULTS)
    override = getattr(settings, "RATE_LIMIT", None) or {}
    for key, value in override.items():
        if key == "PENALTY":
            cfg["PENALTY"].update(value)
        else:
            cfg[key] = value
    return cfg
