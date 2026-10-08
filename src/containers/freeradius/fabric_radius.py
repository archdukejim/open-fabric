"""fabric's 802.1X policy, called by FreeRADIUS's python3 module
(mods/fabric_policy).

authorize() runs in three places:
  - fabric-check-eap-tls, after the client certificate chained to the
    fabric CA: the device linked to that certificate's fingerprint must be
    enabled and hold network:eap-tls;
  - fabric-inner-tunnel, inside EAP-TTLS: a person's user name and password
    (PAP), checked by binding to the site's DC; they must be in a group mapped for
    802.1X (radius_people);
  - the main server for anything that is not EAP: MAB, the switch asking
    for a MAC (User-Name = the MAC); the device with that MAC must be
    enabled and hold network:mab.
post_auth() runs in fabric-inner-tunnel once the domain accepted a PEAP
(EAP-MSCHAPv2) answer through ntlm_auth: the person, or the domain machine
of this site, must be in a group mapped for 802.1X (2.1.11.3).
Accepted: the role's VLAN as Tunnel-Private-Group-Id (none: the port's
default). Refused, or the directory cannot be asked: Access-Reject (fail
closed). Every decision is logged as one `fabric: ...` line (the auth log
`fabricctl radius log` and the web UI read).
"""
import os
import re

import radiusd

from check_peap import check_peap
from check_person import check_person
from lookup_device import lookup_device
from normalize_mac import normalize_mac

FP_CACHE = "/run/freeradius/fp"


def _log(decision, method, **kv):
    """Purpose: log one decision as a single `fabric: …` line in FreeRADIUS's auth log (what
             `fabricctl radius log` and the web UI read).
    Inputs:  decision — "ACCEPT" or "REJECT"; method — "eap-tls", "eap-ttls" or "mab"; kv — key=value details
             (spaces in values become "_", empty values "-").
    Returns: None.
    Fails:   never in practice (radiusd.radlog).
    Feeds:   _decide, _decide_person, authorize."""
    radiusd.radlog(radiusd.L_AUTH, "fabric: %s method=%s %s" % (
        decision, method, " ".join("%s=%s" % (k, str(v).replace(" ", "_") or "-") for k, v in kv.items())))


def _reply(vlan):
    """Purpose: the reply attributes that put a client on a VLAN.
    Inputs:  vlan — int/str VLAN id, or None/0 for the port's default VLAN.
    Returns: tuple of (attribute, ":=", value) for Tunnel-Type, Tunnel-Medium-Type and Tunnel-Private-Group-Id;
             () when there is no VLAN.
    Fails:   never.
    Feeds:   _decide, _decide_person."""
    if not vlan:
        return ()
    return (("Tunnel-Type", ":=", "VLAN"), ("Tunnel-Medium-Type", ":=", "IEEE-802"),
            ("Tunnel-Private-Group-Id", ":=", str(vlan)))


def _decide(method, attribute, value, permission, where):
    """Purpose: decide a device (EAP-TLS by certificate fingerprint, or MAB by MAC) and log it; fail closed.
    Inputs:  method — str for the log; attribute — "fabricCertFingerprint" or "macAddress"; value — str;
             permission — "network:eap-tls" or "network:mab"; where — dict of log details (mac, nas, …).
    Returns: radiusd.RLM_MODULE_REJECT, or (RLM_MODULE_OK, VLAN reply attributes, (("Auth-Type", ":=",
             "Accept"),)).
    Fails:   never raises — any exception from lookup_device (directory down, bad data) becomes a logged reject.
    Feeds:   authorize."""
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
    """Purpose: decide a person joining by user name and password (EAP-TTLS) and log it; fail closed.
    Inputs:  uid — str user name; password — str; where — dict of log details.
    Returns: radiusd.RLM_MODULE_REJECT, or (RLM_MODULE_OK, VLAN reply attributes, Auth-Type := Accept).
    Fails:   never raises — any exception from check_person becomes a logged reject.
    Feeds:   authorize."""
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


def _decide_peap(name, where):
    """Purpose: decide an account the domain accepted over PEAP (a person, or a machine of this site) and log it;
             fail closed.
    Inputs:  name — str, the account's sAMAccountName (a machine's ends in "$"); where — dict of log details.
    Returns: radiusd.RLM_MODULE_REJECT, or (RLM_MODULE_OK, VLAN reply attributes, ()).
    Fails:   never raises — any exception from check_peap becomes a logged reject.
    Feeds:   post_auth."""
    who = "machine" if name.endswith("$") else "person"
    try:
        found = check_peap(name)
    except Exception as exc:          # directory down: never let anyone in
        _log("REJECT", "peap", reason="directory_error:" + type(exc).__name__, **{who: name or "-"}, **where)
        return radiusd.RLM_MODULE_REJECT
    if not found["allowed"]:
        _log("REJECT", "peap", reason=found["reason"], **{who: found["account"]}, **where)
        return radiusd.RLM_MODULE_REJECT
    _log("ACCEPT", "peap", group=found["group"], vlan=found["vlan"] or "-", **{who: found["account"]}, **where)
    return radiusd.RLM_MODULE_OK, _reply(found["vlan"]), ()


def instantiate(p):
    """Purpose: FreeRADIUS python3 module start hook (func_instantiate in mods/fabric_policy); nothing to set up.
    Inputs:  p — the configuration pairs FreeRADIUS passes (unused).
    Returns: radiusd.RLM_MODULE_OK.
    Fails:   never.
    Feeds:   FreeRADIUS (mods/fabric_policy)."""
    return radiusd.RLM_MODULE_OK


def authorize(p):
    """Purpose: FreeRADIUS authorize hook: route the request to the right decision — a person inside
             EAP-TTLS (Tmp-String-0 "fabric-people", set by sites/inner-tunnel), a device after EAP-TLS (by the
             fingerprint record_fingerprint stored under the certificate serial), EAP still in progress (no-op),
             or MAB (User-Name must be the calling MAC).
    Inputs:  p — tuple of (attribute, value) request pairs from FreeRADIUS (the first value of each attribute is
             used). Reads /run/freeradius/fp/<serial>.
    Returns: radiusd.RLM_MODULE_REJECT, RLM_MODULE_NOOP (EAP in progress), or (RLM_MODULE_OK, reply attributes,
             config attributes) from _decide / _decide_person.
    Fails:   never raises for a missing fingerprint or a directory error (logged reject); an exception here
             would make FreeRADIUS fail the module, which also rejects.
    Feeds:   FreeRADIUS (func_authorize in mods/fabric_policy; called from sites fabric, check-eap-tls,
             inner-tunnel)."""
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


def post_auth(p):
    """Purpose: FreeRADIUS post-auth hook: in fabric-inner-tunnel, once the domain accepted a PEAP answer
             (Tmp-String-0 "fabric-peap", the account in Tmp-String-1 as mschap names it), decide it; anywhere else
             nothing to do.
    Inputs:  p — tuple of (attribute, value) request pairs from FreeRADIUS.
    Returns: radiusd.RLM_MODULE_NOOP, radiusd.RLM_MODULE_REJECT, or (RLM_MODULE_OK, reply attributes, ()).
    Fails:   never raises for a directory error (logged reject).
    Feeds:   FreeRADIUS (func_post_auth in mods/fabric_policy; called from sites/inner-tunnel)."""
    req = {}
    for attr, value in p or ():
        req.setdefault(attr, str(value))
    if req.get("Tmp-String-0") != "fabric-peap":
        return radiusd.RLM_MODULE_NOOP
    where = {"mac": normalize_mac(req.get("Calling-Station-Id")) or req.get("Calling-Station-Id", "-"),
             "nas": req.get("NAS-Identifier") or req.get("NAS-IP-Address") or "-"}
    return _decide_peap(req.get("Tmp-String-1", ""), where)
