import ipaddress
import re

from fabriclib.common.errors import ValidationError

LABEL = r"[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?"
NAME_RE = re.compile(rf"^(?:@|\*|(?:\*\.)?{LABEL}(?:\.{LABEL})*)$")
HOST_RE = re.compile(rf"^{LABEL}(?:\.{LABEL})*\.?$")


def _int(value, lo, hi, field):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number")
    if not lo <= n <= hi:
        raise ValidationError(f"{field} must be between {lo} and {hi}")
    return n


def _host(value, field):
    value = (value or "").strip()
    if not HOST_RE.match(value):
        raise ValidationError(f"invalid {field}")
    return value


def validate_record(rtype, form):
    """Build a vars.yaml record from user input. Anything that could inject
    zone-file syntax (quotes, newlines, `$INCLUDE`, bad labels) is rejected."""
    name = (form.get("name") or "").strip()
    if not NAME_RE.match(name):
        raise ValidationError("invalid record name")
    if rtype == "A":
        try:
            return {"name": name, "ip": str(ipaddress.IPv4Address((form.get("ip") or "").strip()))}
        except ValueError:
            raise ValidationError("invalid IPv4 address")
    if rtype == "AAAA":
        try:
            return {"name": name, "ip": str(ipaddress.IPv6Address((form.get("ip") or "").strip()))}
        except ValueError:
            raise ValidationError("invalid IPv6 address")
    if rtype == "CNAME":
        return {"name": name, "canonical": _host(form.get("target"), "CNAME target")}
    if rtype == "MX":
        return {"name": name, "priority": _int(form.get("priority"), 0, 65535, "priority"),
                "exchange": _host(form.get("target"), "mail exchange")}
    if rtype == "TXT":
        text = form.get("text") or ""
        if not text or len(text) > 255 or any(c in text for c in '"\\\r\n'):
            raise ValidationError("TXT must be 1-255 chars without quotes, backslashes or newlines")
        return {"name": name, "text": text}
    if rtype == "SRV":
        return {"name": name, "priority": _int(form.get("priority"), 0, 65535, "priority"),
                "weight": _int(form.get("weight"), 0, 65535, "weight"),
                "port": _int(form.get("port"), 1, 65535, "port"),
                "target": _host(form.get("target"), "SRV target")}
    raise ValidationError("unsupported record type")
