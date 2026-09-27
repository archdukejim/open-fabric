"""Operations exposed by the web UI. Shares state and code paths with fabricctl:
the same vars.yaml, the same `interactive.py --apply`, the same audit log."""
import datetime
import fcntl
import ipaddress
import os
import re
import subprocess
import sys
from contextlib import contextmanager

LIB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB_DIR)
import interactive  # noqa: E402  (fabricctl's own helpers)

FABRIC_DIR = os.path.dirname(LIB_DIR)
VARS_FILE = interactive.CUSTOM_VARS_FILE
AUDIT_FILE = os.path.join(FABRIC_DIR, "archive", "audit.log")
LOCK_FILE = os.path.join(FABRIC_DIR, "config", ".webui.lock")

SERVICES = ["nginx", "bind9", "stepca", "ldap", "postgres", "keycloak", "webui"]
RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]

LABEL = r"[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?"
NAME_RE = re.compile(rf"^(?:@|\*|(?:\*\.)?{LABEL}(?:\.{LABEL})*)$")
HOST_RE = re.compile(rf"^{LABEL}(?:\.{LABEL})*\.?$")


class ValidationError(ValueError):
    pass


@contextmanager
def vars_lock():
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def audit(actor, action, detail):
    os.makedirs(os.path.dirname(AUDIT_FILE), mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] User: {actor} (web) | Action: {action} | {detail}\n"
    with open(AUDIT_FILE, "a") as f:
        f.write(line.replace("\r", " "))


def read_audit(limit=200):
    try:
        with open(AUDIT_FILE) as f:
            return f.readlines()[-limit:][::-1]
    except FileNotFoundError:
        return []


def version_info():
    def read(name):
        try:
            with open(os.path.join(FABRIC_DIR, name)) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
    return {"version": read("VERSION") or "unknown", "build": read("BUILD")}


def service_status():
    result = []
    for svc in SERVICES:
        try:
            res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
            state = res.stdout.strip() or "unknown"
        except subprocess.TimeoutExpired:
            state = "timeout"
        if state != "inactive" or os.path.exists(f"/etc/systemd/system/{svc}.service"):
            result.append((svc, state))
    return result


# -- DNS -------------------------------------------------------------------
def _data():
    return interactive.load_yaml(VARS_FILE)


def zone_label(data, key):
    return data.get("domain", "") if key == "dynamic_zone_var" else key


def list_zones():
    data = _data()
    zones = []
    for key, zone in (data.get("dns") or {}).items():
        count = sum(len(v) for k, v in (zone or {}).items() if isinstance(v, list))
        zones.append({"key": key, "name": zone_label(data, key), "records": count})
    return zones


def zone_detail(key):
    data = _data()
    zone = (data.get("dns") or {}).get(key)
    if zone is None:
        raise ValidationError("unknown zone")
    records = []
    for rtype in RECORD_TYPES:
        for idx, rec in enumerate(zone.get(rtype) or []):
            records.append({"type": rtype, "index": idx, "name": rec.get("name") or "",
                            "value": interactive.format_record_value(rtype, rec)})
    name = zone_label(data, key)
    status = re.sub(r"\x1b\[[0-9;]*m", "", interactive.zone_sync_status(name))
    return {"key": key, "name": name, "records": records, "status": status}


def _int(value, lo, hi, field):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number")
    if not lo <= n <= hi:
        raise ValidationError(f"{field} must be between {lo} and {hi}")
    return n


def build_record(rtype, form):
    name = (form.get("name") or "").strip()
    if not NAME_RE.match(name):
        raise ValidationError("invalid record name")
    if rtype == "A":
        try:
            return {"name": name, "ip": str(ipaddress.IPv4Address(form.get("ip", "").strip()))}
        except ValueError:
            raise ValidationError("invalid IPv4 address")
    if rtype == "AAAA":
        try:
            return {"name": name, "ip": str(ipaddress.IPv6Address(form.get("ip", "").strip()))}
        except ValueError:
            raise ValidationError("invalid IPv6 address")
    if rtype == "CNAME":
        target = form.get("target", "").strip()
        if not HOST_RE.match(target):
            raise ValidationError("invalid CNAME target")
        return {"name": name, "canonical": target}
    if rtype == "MX":
        target = form.get("target", "").strip()
        if not HOST_RE.match(target):
            raise ValidationError("invalid mail exchange")
        return {"name": name, "priority": _int(form.get("priority"), 0, 65535, "priority"), "exchange": target}
    if rtype == "TXT":
        text = form.get("text", "")
        if not text or len(text) > 255 or any(c in text for c in '"\\\r\n'):
            raise ValidationError("TXT must be 1-255 chars without quotes, backslashes or newlines")
        return {"name": name, "text": text}
    if rtype == "SRV":
        target = form.get("target", "").strip()
        if not HOST_RE.match(target):
            raise ValidationError("invalid SRV target")
        return {"name": name, "priority": _int(form.get("priority"), 0, 65535, "priority"),
                "weight": _int(form.get("weight"), 0, 65535, "weight"),
                "port": _int(form.get("port"), 1, 65535, "port"), "target": target}
    raise ValidationError("unsupported record type")


def add_record(actor, key, rtype, form):
    record = build_record(rtype, form)
    with vars_lock():
        data = _data()
        zone = (data.get("dns") or {}).get(key)
        if zone is None:
            raise ValidationError("unknown zone")
        existing = zone.setdefault(rtype, [])
        if any(r.get("name") == record["name"] and rtype == "CNAME" for r in existing):
            raise ValidationError("a CNAME with that name already exists")
        existing.append(record)
        interactive.save_yaml(VARS_FILE, data)
    audit(actor, "DNS_ADD", f"zone={key} {rtype} {record}")
    return record


def delete_record(actor, key, rtype, index, expected_name):
    with vars_lock():
        data = _data()
        records = ((data.get("dns") or {}).get(key) or {}).get(rtype) or []
        if not 0 <= index < len(records) or (records[index].get("name") or "") != expected_name:
            raise ValidationError("record changed since the page was loaded; reload and try again")
        removed = records.pop(index)
        if not records:
            del data["dns"][key][rtype]
        interactive.save_yaml(VARS_FILE, data)
    audit(actor, "DNS_DELETE", f"zone={key} {rtype} {removed}")
    return removed


def apply_changes(actor):
    """Run the same apply as `fabricctl --apply`. Returns (ok, output)."""
    with vars_lock():
        res = subprocess.run([sys.executable, os.path.join(LIB_DIR, "interactive.py"), "--apply"],
                             capture_output=True, text=True, timeout=900,
                             env={**os.environ, "TERM": "dumb"})
    output = re.sub(r"\x1b\[[0-9;]*m", "", res.stdout + res.stderr)
    audit(actor, "APPLY", f"exit={res.returncode}")
    return res.returncode == 0, output
