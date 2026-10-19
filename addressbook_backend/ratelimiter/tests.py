from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from .limiter import PenaltyBox, SlidingWindowLimiter
from .utils import get_client_ip, ip_bucket


class FakeClock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class SlidingWindowTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.clock = FakeClock()
        self.lim = SlidingWindowLimiter(cache, self.clock)

    def test_allows_up_to_limit_then_rejects_with_retry_after(self):
        for _ in range(3):
            self.assertTrue(self.lim.hit("b", 3, 60).allowed)
        hit = self.lim.hit("b", 3, 60)
        self.assertFalse(hit.allowed)
        self.assertGreaterEqual(hit.retry_after, 1)
        self.assertLessEqual(hit.retry_after, 120)

    def test_rejected_requests_do_not_consume_quota(self):
        for _ in range(3):
            self.lim.hit("b", 3, 60)
        for _ in range(10):
            self.lim.hit("b", 3, 60)
        self.clock.t += 130  # two full windows later everything has decayed
        self.assertTrue(self.lim.hit("b", 3, 60).allowed)

    def test_retry_after_is_honest(self):
        for _ in range(3):
            self.lim.hit("b", 3, 60)
        wait = self.lim.hit("b", 3, 60).retry_after
        self.clock.t += wait
        self.assertTrue(self.lim.hit("b", 3, 60).allowed)

    def test_no_double_burst_at_window_boundary(self):
        self.clock.t = 1_000_000 - (1_000_000 % 60) + 59  # last second of a window
        for _ in range(5):
            self.assertTrue(self.lim.hit("b", 5, 60).allowed)
        self.clock.t += 2  # new fixed window, but the sliding view still sees the burst
        self.assertFalse(self.lim.hit("b", 5, 60).allowed)

    def test_cost(self):
        self.assertTrue(self.lim.hit("b", 4, 60, cost=2).allowed)
        self.assertTrue(self.lim.hit("b", 4, 60, cost=2).allowed)
        self.assertFalse(self.lim.hit("b", 4, 60, cost=2).allowed)


class PenaltyTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.clock = FakeClock()
        cfg = {"STRIKES": 3, "STRIKE_WINDOW": 600, "BASE_BLOCK": 60, "MAX_BLOCK": 200, "MEMORY": 86400}
        self.box = PenaltyBox(cache, "t", cfg, self.clock)

    def test_block_escalates_and_is_capped(self):
        durations = []
        for _ in range(4):
            for _ in range(2):
                self.assertEqual(self.box.strike("ip", "1.1.1.1"), 0)
            durations.append(self.box.strike("ip", "1.1.1.1"))
        self.assertEqual(durations, [60, 120, 200, 200])

    def test_block_expires_and_clear_works(self):
        for _ in range(3):
            self.box.strike("ip", "x")
        self.assertGreater(self.box.blocked_for("ip", "x"), 0)
        self.clock.t += 61
        self.assertEqual(self.box.blocked_for("ip", "x"), 0)
        for _ in range(3):
            self.box.strike("ip", "y")
        self.box.clear("ip", "y")
        self.assertEqual(self.box.blocked_for("ip", "y"), 0)


class IpTests(SimpleTestCase):
    class Req:
        def __init__(self, **meta):
            self.META = meta

    def test_uses_rightmost_trusted_entry_not_spoofable_left(self):
        r = self.Req(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.9")
        self.assertEqual(str(get_client_ip(r, 1)), "203.0.113.9")

    def test_ignores_xff_without_trusted_proxy(self):
        r = self.Req(REMOTE_ADDR="198.51.100.2", HTTP_X_FORWARDED_FOR="6.6.6.6")
        self.assertEqual(str(get_client_ip(r, 0)), "198.51.100.2")

    def test_ipv6_collapsed_to_slash_64(self):
        a = get_client_ip(self.Req(REMOTE_ADDR="2001:db8:1:2::1"), 0)
        b = get_client_ip(self.Req(REMOTE_ADDR="2001:db8:1:2:ffff::9"), 0)
        self.assertEqual(ip_bucket(a), ip_bucket(b))


RL = {
    "TRUSTED_PROXY_COUNT": 0,
    "GLOBAL": {"ip": [(1000, 3600)]},
    "RULES": [
        {"name": "auth-login", "path": r"^/api/auth/login/$", "methods": ["POST"],
         "limits": {"ip": [(50, 3600)], "username": [(3, 3600)]}},
        {"name": "contacts-search", "path": r"^/api/contacts/search/$",
         "limits": {"user": [(2, 3600)]}},
        {"name": "contacts", "path": r"^/api/contacts/", "limits": {"user": [(100, 3600)]}},
    ],
    "PENALTY": {"STRIKES": 2, "BASE_BLOCK": 60},
}


@override_settings(RATE_LIMIT=RL)
class MiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()

    def _login(self, username="bob", password="wrong", ip="198.51.100.7"):
        return self.client.post("/api/auth/login/", {"username": username, "password": password},
                                content_type="application/json", REMOTE_ADDR=ip)

    def test_login_is_limited_per_username_across_ips(self):
        User.objects.create_user("bob", password="right-pass-1")
        codes = [self._login(ip=f"198.51.100.{i}").status_code for i in range(1, 4)]
        self.assertEqual(codes, [401, 401, 401])
        last = self._login(ip="203.0.113.50")  # a brand-new IP, same account
        self.assertEqual(last.status_code, 429)
        self.assertIn("Retry-After", last)
        self.assertEqual(last.json()["code"], "rate_limited")

    def test_other_usernames_unaffected(self):
        for _ in range(4):
            self._login("bob")
        self.assertEqual(self._login("alice").status_code, 401)

    def test_repeat_offender_gets_temporarily_blocked(self):
        for _ in range(3):
            self._login("bob")
        self._login("bob")          # strike 1
        resp = self._login("bob")   # strike 2 -> block
        self.assertEqual(resp.json()["code"], "temporarily_blocked")
        self.assertEqual(resp["Retry-After"], "60")

    def test_authenticated_limit_is_per_user_and_headers_present(self):
        u1 = User.objects.create_user("u1", password="x12345678")
        u2 = User.objects.create_user("u2", password="x12345678")
        h1 = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(u1)}"}
        h2 = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(u2)}"}
        r = self.client.get("/api/contacts/search/?q=a", **h1)  # cost 1 default
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-RateLimit-Remaining", r)
        self.client.get("/api/contacts/search/?q=a", **h1)
        self.assertEqual(self.client.get("/api/contacts/search/?q=a", **h1).status_code, 429)
        self.assertEqual(self.client.get("/api/contacts/search/?q=a", **h2).status_code, 200)

    def test_forged_token_is_treated_as_anonymous(self):
        r = self.client.get("/api/contacts/", HTTP_AUTHORIZATION="Bearer not.a.token")
        self.assertEqual(r.status_code, 401)  # reaches DRF, not rate-limited

    @override_settings(RATE_LIMIT={**RL, "ALLOWLIST": ["198.51.100.0/24"]})
    def test_allowlist_bypasses(self):
        for _ in range(10):
            self.assertEqual(self._login().status_code, 401)

    @override_settings(RATE_LIMIT={**RL, "BLOCKLIST": ["198.51.100.7"]})
    def test_blocklist_rejects(self):
        self.assertEqual(self._login().status_code, 403)

    @override_settings(RATE_LIMIT={**RL, "ENABLED": False})
    def test_can_be_disabled(self):
        for _ in range(10):
            self.assertEqual(self._login().status_code, 401)
