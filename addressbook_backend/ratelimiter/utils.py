import hashlib
import ipaddress


def _parse_ip(value):
    try:
        return ipaddress.ip_address(value.strip())
    except (ValueError, AttributeError):
        return None


def get_client_ip(request, trusted_proxy_count=1):
    """Best-effort real client address.

    X-Forwarded-For can be forged by the client, but every trusted proxy appends the
    address it saw to the *right* end.  So with N trusted proxies the real client is the
    N-th entry from the right; anything further left is attacker-controlled and ignored.
    """
    remote = request.META.get("REMOTE_ADDR", "")
    ip = _parse_ip(remote)
    if trusted_proxy_count > 0:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= trusted_proxy_count:
            candidate = _parse_ip(parts[-trusted_proxy_count])
            if candidate is not None:
                ip = candidate
    return ip


def ip_bucket(ip):
    """String used as the rate-limit key. IPv6 clients get a whole /64 each, so an
    attacker can't dodge limits by rotating addresses inside their own prefix."""
    if ip is None:
        return "unknown"
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address) + "/64"
    return str(ip)


def ip_in_list(ip, entries):
    if ip is None:
        return False
    for entry in entries or []:
        try:
            if "/" in str(entry):
                if ip in ipaddress.ip_network(entry, strict=False):
                    return True
            elif ip == ipaddress.ip_address(str(entry).strip()):
                return True
        except ValueError:
            continue
    return False


def hash_value(value):
    """Short stable hash - keeps usernames out of cache keys (privacy, key-safety)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
