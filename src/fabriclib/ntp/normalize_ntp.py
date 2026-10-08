import ipaddress
import re

from fabriclib.common.errors import ValidationError

HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
                     r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
FLAGS = ("nts", "pool", "prefer")


def normalize_ntp(v):
    """Purpose: check the time settings (manual 1.13.1.5) before anything is rendered.
    Inputs:  v — the vars dict: ntp_servers (list of "<host> [nts] [pool] [prefer]", host a DNS name or an IP
             address), ntp_serve, ntp_set_clock (booleans).
    Returns: [{"host", "nts", "pool", "prefer"}] — one per ntp_servers entry, in order, flags as booleans.
    Fails:   ValidationError for a list that is not a list of strings, a bad host, an unknown or repeated flag, a
             duplicate host, or ntp_serve/ntp_set_clock that are not booleans.
    Feeds:   deploy/check_settings (apply, before rendering), chrony_settings; tests/ntp/run.py, tests/render.py."""
    for key in ("ntp_serve", "ntp_set_clock"):
        if not isinstance(v.get(key, True), bool):
            raise ValidationError(f"{key}: true or false")
    entries = v.get("ntp_servers")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ValidationError('ntp_servers: a list like ["time.cloudflare.com nts", "192.168.4.1"]')
    servers, seen = [], set()
    for entry in entries:
        words = str(entry).split() if isinstance(entry, str) else []
        if not words:
            raise ValidationError(f"ntp_servers entry {entry!r}: \"<host> [nts] [pool] [prefer]\"")
        host, flags = words[0], words[1:]
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not HOST_RE.match(host):
                raise ValidationError(f"ntp_servers entry {entry!r}: {host!r} is not a host name or address")
        bad = [f for f in flags if f not in FLAGS]
        if bad or len(set(flags)) != len(flags):
            raise ValidationError(f"ntp_servers entry {entry!r}: flags are nts, pool and prefer, each once")
        if host.lower() in seen:
            raise ValidationError(f"ntp_servers: {host} is listed twice")
        seen.add(host.lower())
        servers.append({"host": host, **{f: f in flags for f in FLAGS}})
    return servers
