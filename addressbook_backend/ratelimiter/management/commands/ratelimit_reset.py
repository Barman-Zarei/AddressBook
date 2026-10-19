from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError

from ratelimiter.conf import get_config
from ratelimiter.limiter import PenaltyBox
from ratelimiter.utils import hash_value, ip_bucket
import ipaddress


class Command(BaseCommand):
    help = "Remove the block / strike history of an IP, user id or username."

    def add_arguments(self, parser):
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument("--ip")
        g.add_argument("--user-id")
        g.add_argument("--username")

    def handle(self, *args, **o):
        cfg = get_config()
        box = PenaltyBox(caches["default"], cfg["KEY_PREFIX"], cfg["PENALTY"])
        if o["ip"]:
            try:
                value = ip_bucket(ipaddress.ip_address(o["ip"]))
            except ValueError:
                raise CommandError("Invalid IP address.")
            box.clear("ip", value)
        elif o["user_id"]:
            box.clear("user", o["user_id"])
        else:
            box.clear("username", hash_value(o["username"].strip().lower()))
        self.stdout.write(self.style.SUCCESS("Penalty state cleared."))
