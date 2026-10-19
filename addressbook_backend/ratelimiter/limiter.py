"""Core algorithms: sliding-window counter + escalating penalty box.

Sliding-window *counter*: two adjacent fixed windows are kept and the previous one is
weighted by how much of it still overlaps the sliding window. It is O(1) in memory per
key (unlike a request log), has no burst-at-the-boundary problem (unlike fixed windows)
and only needs atomic ``incr`` from the cache, so it behaves correctly with Redis and
several gunicorn workers.
"""

import logging
import math
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Hit:
    allowed: bool
    limit: int
    window: int
    remaining: int
    retry_after: int  # seconds, 0 when allowed
    reset: int        # seconds until the current window rolls over
    key: str = ""
    cost: int = 1


def _incr(cache, key, delta, ttl):
    try:
        return cache.incr(key, delta)
    except ValueError:  # key missing / expired
        cache.add(key, 0, ttl)
        try:
            return cache.incr(key, delta)
        except ValueError:
            cache.set(key, delta, ttl)
            return delta


class SlidingWindowLimiter:
    def __init__(self, cache, clock=time.time):
        self.cache = cache
        self.clock = clock

    def hit(self, bucket, limit, window, cost=1):
        now = self.clock()
        idx = int(now // window)
        elapsed = now - idx * window
        frac = elapsed / window
        cur_key = f"{bucket}:{idx}"
        prev_key = f"{bucket}:{idx - 1}"

        cur = _incr(self.cache, cur_key, cost, window * 2)
        prev = self.cache.get(prev_key) or 0
        cur_before = cur - cost
        estimate = prev * (1 - frac) + cur
        reset = max(1, math.ceil(window - elapsed))

        if estimate <= limit:
            return Hit(True, limit, window, max(0, int(limit - estimate)), 0, reset, cur_key, cost)

        # Rejected: give the quota back so refused requests don't extend the penalty.
        self.undo(Hit(False, limit, window, 0, 0, reset, cur_key, cost))
        retry = self._retry_after(prev, cur_before, cost, limit, window, frac)
        return Hit(False, limit, window, 0, retry, reset, cur_key, cost)

    def undo(self, hit):
        try:
            self.cache.decr(hit.key, hit.cost)
        except ValueError:
            pass

    @staticmethod
    def _retry_after(prev, cur_before, cost, limit, window, frac):
        room = limit - cur_before - cost
        if prev > 0 and room >= 0:
            wait = max(0.0, (1 - room / prev) - frac) * window
        else:
            # Not enough room even with the old window gone -> wait for the rollover,
            # then for the (new) previous window to decay.
            wait = (1 - frac) * window
            room2 = limit - cost
            if cur_before > 0 and room2 >= 0:
                wait += max(0.0, 1 - room2 / cur_before) * window
        return max(1, math.ceil(wait))


class PenaltyBox:
    """Clients that keep getting rejected are blocked for 1x, 2x, 4x ... the base time."""

    def __init__(self, cache, prefix, cfg, clock=time.time):
        self.cache = cache
        self.prefix = prefix
        self.cfg = cfg
        self.clock = clock

    def _key(self, kind, dim, value):
        return f"{self.prefix}:pen:{kind}:{dim}:{value}"

    def blocked_for(self, dim, value):
        until = self.cache.get(self._key("block", dim, value))
        if not until:
            return 0
        remaining = until - self.clock()
        return math.ceil(remaining) if remaining > 0 else 0

    def strike(self, dim, value):
        """Register one rejected request. Returns the new block length in seconds if
        this strike started a block, else 0."""
        cfg = self.cfg
        strikes = _incr(self.cache, self._key("strike", dim, value), 1, cfg["STRIKE_WINDOW"])
        if strikes < cfg["STRIKES"]:
            return 0
        self.cache.delete(self._key("strike", dim, value))
        level_key = self._key("level", dim, value)
        level = min((self.cache.get(level_key) or 0) + 1, 30)
        self.cache.set(level_key, level, cfg["MEMORY"])
        duration = int(min(cfg["BASE_BLOCK"] * (2 ** (level - 1)), cfg["MAX_BLOCK"]))
        self.cache.set(self._key("block", dim, value), self.clock() + duration, duration)
        logger.warning("rate-limit: blocked %s=%s for %ss (level %s)", dim, value, duration, level)
        return duration

    def clear(self, dim, value):
        for kind in ("strike", "level", "block"):
            self.cache.delete(self._key(kind, dim, value))
