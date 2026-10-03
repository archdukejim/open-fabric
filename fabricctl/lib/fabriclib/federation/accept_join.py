import base64
import datetime
import os
import hashlib
import hmac
import ipaddress
import time

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.federation_lock import federation_lock
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.common.save_registry import save_registry
from fabriclib.federation.common.signing_capacity import signing_capacity
from fabriclib.federation.constants import DOMAIN_RE, SITE_NAME_RE
from fabriclib.federation.network_conflicts import network_conflicts
from fabriclib.federation.read_address_plan import read_address_plan
from fabriclib.federation.site_networks import site_networks
from fabriclib.pki.sign_site_ca import sign_site_ca
from fabriclib.secrets.load_secrets import load_secrets
from fabriclib.secrets.save_secrets import save_secrets

_ORG_KEYS = ("friendly_name", "cert_country", "cert_province", "cert_city", "cert_org", "cert_ou")
REFUSED = "the invitation is not valid (unknown, used, withdrawn or expired)"


def _port(value):
    """Purpose: a DNS port a joining site reported, or 53.
    Inputs:  value — anything from the request.
    Returns: int 1..65535 (53 when absent or invalid).
    Fails:   never.
    Feeds:   accept_join (the site record's dns_port)."""
    return int(value) if str(value).isdigit() and 0 < int(value) < 65536 else 53


def _check_networks(v, site, networks):
    """Purpose: refuse a joining site whose networks overlap another site's (manual 2.2.2.6): the
             upstream's copy of the address plan, plus its own networks (the plan may not list them yet).
    Inputs:  v — the upstream's vars; site — the joining site's name; networks — what the request reported
             ([{name, cidr, allow_overlap}]; an older fabric sends none).
    Returns: None.
    Fails:   ValidationError "the site's networks …" for a malformed list, or naming each overlap without an
             allow_overlap reason.
    Feeds:   accept_join."""
    if not isinstance(networks, list) or len(networks) > 256:
        raise ValidationError("the site's networks are not a list")
    mine = []
    for n in networks:
        try:
            cidr = str(ipaddress.ip_network(str(n["cidr"]), strict=False))
        except (KeyError, TypeError, ValueError):
            raise ValidationError("the site's networks are not valid") from None
        mine.append({"name": str(n.get("name") or cidr)[:64], "cidr": cidr,
                     "allow_overlap": str(n.get("allow_overlap") or "")[:200]})
    try:
        plan = read_address_plan(v)
    except (ValidationError, RuntimeError):      # 389-DS not answering: at least this site's own networks
        plan = []
    plan += [{**n, "site": v.get("site_name")} for n in site_networks(v)]
    bad = [c for c in network_conflicts(mine, plan, site) if not c["allowed"]]
    if bad:
        raise ValidationError("; ".join(f"{c['cidr']} overlaps {c['other_cidr']} of site {c['other_site']}"
                                        for c in bad) + ": give the joining site other networks")


def accept_join(v, req, client_ip="", now=None):
    """Purpose: On the upstream: let an invited site join (manual 1.8.4.1 step 3): check the one-time
             invitation, sign the site's intermediate CA with the root key, record the site and use up the
             invitation.
    Inputs:  v — fabric vars: domain, org_domain (default domain), ldap_base_dn, site_name, host_ip,
             hostname_federation, hostname_ldap and
             the organisation settings (friendly_name, cert_*), plus what sign_site_ca reads; req — the join
             request {"id", "secret", "site", "csr", "domain" (the site's own domain), "address" (its IP),
             optional "ldap_host" (its LDAPS name, default ldap.<domain>), optional "networks" (its LAN and DHCP
             subnets: refused when they overlap another site's, _check_networks)};
             client_ip — str for the audit; now — epoch seconds, default time.time().
    Returns: {"root": PEM, "cert": PEM of the site's intermediate (path length: the invitation's nest), "chain":
             PEM of the CAs between it and the root ("" when this is the root site; this site's CA and its
             parents when this is a site and the new one is nested under it), "dns": {"key": "fed-<site>",
             "algorithm", "secret", "port"} — the TSIG key both sites sign zone transfers with (port: this
             site's published DNS port) (kept here in fabric's
             secrets as federation_tsig[site]; manual 1.8 M4), "directory": {"secret", "ldap_host",
             "ldap_port"} — the directory link's secret (replication both ways, kept here as
             federation_replication[site]; §3.2a) and this site's LDAPS name, "org": {"org_domain", "ldap_base_dn",
             friendly_name, cert_*}, "upstream": {"site_name", "domain", "host", "address"}}.
    Fails:   ValidationError "the join request is incomplete"; overlapping networks (_check_networks, before
             anything is signed or recorded); "the site's domain/address is not valid" or
             "a site cannot use this site's domain"; REFUSED for an unknown, expired or wrong secret (one message,
             so a caller learns nothing about which); "the invitation was made for site <x>"; "site <x> has
             joined already"; sign_site_ca's messages (the invitation is kept, so a corrected request can
             retry); ValidationError from load_secrets/save_secrets; OSError.
    Feeds:   the federation endpoint (fabricctl/lib/federation/server.py, POST /v1/join).
    Notes:   the secret is compared by its SHA-256 in constant time; audited as FED_JOIN (actor "site:<name>",
             with the client address) and, on refusal, FED_JOIN_REFUSED."""
    now = int(now if now is not None else time.time())
    if not isinstance(req, dict) or not all(isinstance(req.get(k), str) and req.get(k)
                                            for k in ("id", "secret", "site", "csr", "domain", "address")):
        raise ValidationError("the join request is incomplete")
    site, domain = req["site"].strip().lower(), req["domain"].strip().lower().rstrip(".")
    fed_host = str(req.get("federation_host") or "").strip().lower()
    ldap_host = str(req.get("ldap_host") or "").strip().lower()
    if not SITE_NAME_RE.match(site) or not DOMAIN_RE.match(domain):
        raise ValidationError("the site's name or domain is not valid")
    if domain == v["domain"]:
        raise ValidationError("a site cannot use this site's domain")
    try:
        ipaddress.ip_address(req["address"])
    except ValueError:
        raise ValidationError("the site's address is not valid") from None
    with federation_lock():
        invites = load_secrets(v=v).get("federation_invitations") or {}
        entry = invites.get(req["id"]) or {}
        digest = hashlib.sha256(req["secret"].encode()).hexdigest()
        if not (entry and entry.get("expires", 0) > now and hmac.compare_digest(entry.get("sha256", ""), digest)):
            write_audit(f"site:{site}", "FED_JOIN_REFUSED", f"id={req['id'][:16]} from={client_ip}", "federation")
            raise ValidationError(REFUSED)
        if entry.get("site") != site:
            raise ValidationError(f"the invitation was made for site {entry.get('site')}")
        registry = load_registry()
        if site in registry["sites"]:
            raise ValidationError(f"site {site} has joined already")
        _check_networks(v, site, req.get("networks") or [])     # invitation verified first: no probing the plan
        cap = signing_capacity(v)
        signed = sign_site_ca(v, f"site:{site}", site, req["csr"], source="federation",
                              nest=int(entry.get("nest") or 0), as_parent=cap["as_parent"])
        tsig = base64.b64encode(os.urandom(32)).decode()       # the DNS link to this site (zone transfers)
        repl = base64.b64encode(os.urandom(32)).decode()       # the directory link (replication both ways, M5)
        stored = load_secrets(v=v)
        save_secrets({"federation_invitations": {i: e for i, e in invites.items() if i != req["id"]},
                      "federation_tsig": dict(stored.get("federation_tsig") or {}, **{site: tsig}),
                      "federation_replication": dict(stored.get("federation_replication") or {}, **{site: repl})},
                     v=v)
        registry["sites"][site] = {
            "domain": domain, "address": req["address"],
            "joined": datetime.datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds"),
            "ca_serial": signed["info"]["serial"], "ca_not_after": signed["info"]["not_after"],
            "invited_by": entry.get("actor", ""), "parent": v.get("site_name"), "nest": int(entry.get("nest") or 0),
            "via": entry.get("via") or "", "dns_port": _port(req.get("dns_port")),
            "federation_host": fed_host if DOMAIN_RE.match(fed_host) else f"federation.{domain}",
            "ldap_host": ldap_host if DOMAIN_RE.match(ldap_host) else f"ldap.{domain}", "ldap_port": 636}
        save_registry(registry)
    write_audit(f"site:{site}", "FED_JOIN", f"site={site} domain={domain} address={req['address']} "
                                            f"from={client_ip} ca_serial={signed['info']['serial']}", "federation")
    org = {"org_domain": v.get("org_domain") or v["domain"], "ldap_base_dn": v["ldap_base_dn"],
           **{k: v.get(k) for k in _ORG_KEYS if v.get(k)}}
    return {"root": signed["root"], "cert": signed["cert"], "chain": signed["chain"], "org": org,
            "dns": {"key": f"fed-{site}", "algorithm": "hmac-sha256", "secret": tsig,
                    "port": int(v.get("bind_dns_port") or 53)},
            "directory": {"secret": repl, "ldap_host": v.get("hostname_ldap") or f"ldap.{v['domain']}",
                          "ldap_port": 636},
            "upstream": {"site_name": v.get("site_name"), "domain": v["domain"], "host": v["hostname_federation"],
                         "address": v["host_ip"]}}
