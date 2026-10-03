import datetime
import json
import re
import subprocess

FABRIC_RE = re.compile(r"fabric: (ACCEPT|REJECT) method=(\S+)(.*)$")
INCORRECT_RE = re.compile(r"Login incorrect(?: \((.*?)\))?: \[(.*?)\] \(from client (\S+) port \S+(?: cli (\S+))?")


def list_auth_log(limit=100):
    """Purpose: Recent 802.1X decisions from FreeRADIUS's journal, newest first.
    Inputs:  limit — int, how many to return (default 100); reads up to limit*4 journal entries tagged freeradius via
             journalctl.
    Returns: [{"time", "decision" (ACCEPT / REJECT), "method", "device" (or the person), "person" (bool), "vlan", "mac",
             "nas", "reason"}]; entries from FreeRADIUS's own "Login incorrect" lines carry "identity" instead of
             "person".
    Fails:   FileNotFoundError without journalctl; subprocess.TimeoutExpired after 30 s. Unparseable lines are skipped.
    Feeds:   radius_overview, run_radius_command (log).
    Notes:   fabric's policy logs every decision it makes; a request refused before it (a certificate that does not
             chain to the fabric CA, a broken EAP exchange) shows FreeRADIUS's own reason, unless fabric's REJECT for
             the same MAC came within 2 s. Never secrets: FreeRADIUS logs no passwords (auth_badpass / auth_goodpass are
             off).
    """
    res = subprocess.run(["journalctl", "-t", "freeradius", "-n", str(limit * 4), "-o", "json", "--no-pager"],
                         capture_output=True, text=True, timeout=30)
    entries, last_fabric = [], None
    for line in res.stdout.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        msg = rec.get("MESSAGE") if isinstance(rec.get("MESSAGE"), str) else ""
        when = datetime.datetime.fromtimestamp(int(rec.get("__REALTIME_TIMESTAMP", 0)) / 1e6)
        m = FABRIC_RE.search(msg)
        if m:
            kv = dict(p.split("=", 1) for p in m.group(3).split() if "=" in p)
            entry = {"time": when.isoformat(timespec="seconds"), "decision": m.group(1), "method": m.group(2),
                     "device": kv.get("device") or kv.get("person", "-"),
                     "person": "person" in kv, "vlan": kv.get("vlan", "-"), "mac": kv.get("mac", "-"),
                     "nas": kv.get("nas", "-"), "reason": kv.get("reason", "").replace("_", " ")}
            entries.append(entry)
            last_fabric = (when, entry)
            continue
        m = INCORRECT_RE.search(msg)
        if m:
            mac = (m.group(4) or "-").replace("-", ":").lower()
            if last_fabric and (when - last_fabric[0]).total_seconds() <= 2 \
                    and last_fabric[1]["decision"] == "REJECT" and last_fabric[1]["mac"] == mac:
                continue                          # fabric's own refusal, already listed
            entries.append({"time": when.isoformat(timespec="seconds"), "decision": "REJECT",
                            "method": "eap" if "eap" in (m.group(1) or "") else "-", "device": "-", "vlan": "-",
                            "mac": mac, "nas": m.group(3), "reason": m.group(1) or "refused by FreeRADIUS",
                            "identity": m.group(2)})
    return list(reversed(entries))[:limit]
