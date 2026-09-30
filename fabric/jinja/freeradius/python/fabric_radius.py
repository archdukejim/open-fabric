"""fabric's 802.1X policy, called by FreeRADIUS's python3 module
(mods/fabric_policy).

authorize() runs in three places:
  - fabric-check-eap-tls, after the client certificate chained to the
    fabric CA: the device linked to that certificate's fingerprint must be
    enabled and hold network:eap-tls;
  - fabric-inner-tunnel, inside EAP-TTLS: a person's user name and password
    (PAP), checked by binding to 389-DS; they must be in a group mapped for
    802.1X (radius_people);
  - the main server for anything that is not EAP: MAB, the switch asking
    for a MAC (User-Name = the MAC); the device with that MAC must be
    enabled and hold network:mab.
Accepted: the role's VLAN as Tunnel-Private-Group-Id (none: the port's
default). Refused, or the directory cannot be asked: Access-Reject (fail
closed). Every decision is logged as one `fabric: ...` line (the auth log
`fabricctl radius log` and the web UI read).
"""
import os
import re

import radiusd

from check_person import check_person
from lookup_device import lookup_device
from normalize_mac import normalize_mac

FP_CACHE = "/run/freeradius/fp"


def _log(decision, method, **kv):
    radiusd.radlog(radiusd.L_AUTH, "fabric: %s method=%s %s" % (
        decision, method, " ".join("%s=%s" % (k, str(v).replace(" ", "_") or "-") for k, v in kv.items())))


def _reply(vlan):
    if not vlan:
        return ()
    return (("Tunnel-Type", ":=", "VLAN"), ("Tunnel-Medium-Type", ":=", "IEEE-802"),
            ("Tunnel-Private-Group-Id", ":=", str(vlan)))


def _decide(method, attribute, value, permission, where):
    try:
        found = lookup_device(attribute, value, permission)
    except Exception as exc:          # directory down, bind refused: never let a device in
        _log("REJECT", method, reason="directory_error:" + type(exc).__name__, **where)
        return radiusd.RLM_MODULE_REJECT
    if not found["allowed"]:
        _log("REJECT", method, device=found["device"] or "-", reason=found["reason"], **where)
        return radiusd.RLM_MODULE_REJECT
    _log("ACCEPT", method, device=found["device"], vlan=found["vlan"] or "-", **where)
    return radiusd.RLM_MODULE_OK, _reply(found["vlan"]), (("Auth-Type", ":=", "Accept"),)


def _decide_person(uid, password, where):
    try:
        found = check_person(uid, password)
    except Exception as exc:          # directory down: never let anyone in
        _log("REJECT", "eap-ttls", person=uid, reason="directory_error:" + type(exc).__name__, **where)
        return radiusd.RLM_MODULE_REJECT
    if not found["allowed"]:
        _log("REJECT", "eap-ttls", person=found["person"], reason=found["reason"], **where)
        return radiusd.RLM_MODULE_REJECT
    _log("ACCEPT", "eap-ttls", person=found["person"], group=found["group"], vlan=found["vlan"] or "-", **where)
    return radiusd.RLM_MODULE_OK, _reply(found["vlan"]), (("Auth-Type", ":=", "Accept"),)


def instantiate(p):
    return radiusd.RLM_MODULE_OK


def authorize(p):
    req = {}
    for attr, value in p or ():
        req.setdefault(attr, str(value))
    where = {"mac": normalize_mac(req.get("Calling-Station-Id")) or req.get("Calling-Station-Id", "-"),
             "nas": req.get("NAS-Identifier") or req.get("NAS-IP-Address") or "-"}

    if req.get("Tmp-String-0") == "fabric-people":               # fabric-inner-tunnel (EAP-TTLS)
        return _decide_person(req.get("User-Name", ""), req.get("User-Password", ""), where)

    serial = req.get("TLS-Client-Cert-Serial")
    if serial is not None:                                   # fabric-check-eap-tls
        serial = re.sub(r"[^0-9a-f]", "", serial.lower())
        while len(serial) > 2 and serial.startswith("00"):     # as record_fingerprint keys it
            serial = serial[2:]
        try:
            with open(os.path.join(FP_CACHE, serial)) as f:
                fp = f.read().strip()
        except OSError:
            _log("REJECT", "eap-tls", reason="certificate_not_recorded", serial=serial, **where)
            return radiusd.RLM_MODULE_REJECT
        return _decide("eap-tls", "fabricCertFingerprint", fp, "network:eap-tls", dict(where, sha256=fp))

    if "EAP-Message" in req:                                 # EAP in progress: the eap module's
        return radiusd.RLM_MODULE_NOOP

    # MAB: the switch sends the client's MAC as User-Name (and usually as
    # Calling-Station-Id too); anything else is not a request fabric grants.
    mac = normalize_mac(req.get("User-Name"))
    station = normalize_mac(req.get("Calling-Station-Id"))
    if not mac or (station and station != mac):
        _log("REJECT", "mab", reason="user_name_is_not_the_calling_MAC", user=req.get("User-Name", "-"), **where)
        return radiusd.RLM_MODULE_REJECT
    return _decide("mab", "macAddress", mac, "network:mab", dict(where, mac=mac))
