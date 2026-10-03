import base64
import hashlib
import json
import os
import secrets
import time

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.federation_lock import federation_lock
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.common.signing_capacity import signing_capacity
from fabriclib.federation.common.site_name_problem import site_name_problem
from fabriclib.federation.constants import INVITE_PREFIX, INVITE_TTL_SECONDS
from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.secrets.load_secrets import load_secrets
from fabriclib.secrets.save_secrets import save_secrets


def _org_ous(v):
    """Purpose: the organisation's top-level OU names (a site's part sits beside them: ou=<site>,<base DN>).
    Inputs:  v — fabric vars: ldap_organizational_units.
    Returns: list of str.
    Fails:   never.
    Feeds:   create_invitation."""
    return [ou.get("name") for ou in v.get("ldap_organizational_units") or [] if not ou.get("parent")]


def create_invitation(v, actor, site_name, source="cli", now=None, nest=0, via=""):
    """Purpose: On the upstream: a one-time invitation for a new site to join this fabric (manual 1.8.4.1). Only a hash of its secret is kept.
    Inputs:  v — fabric vars: federation_endpoint (must be true), site_name (this site), domain, org_domain
             (default domain), ldap_base_dn, ldap_organizational_units, host_ip, hostname_federation,
             deploy_base_dir (the root certificate);
             actor — str (audit); site_name — the new site, SITE_NAME_RE, not this site's own, not joined
             already; source — default "cli"; now — epoch seconds, default time.time() (tests); nest — how many
             levels of sites the new site may hold below it (its CA's path length), default 0. Made on the
             root site, the new site attaches flat; made on a site (one that may nest), it is nested under
             that site (manual 1.8.5.1); via — a site that joined this install, through whose
             endpoint the new site joins (a relay: it forwards, signs nothing), default "" (direct).
    Returns: {"invitation": "fabric-join-1.<base64url JSON>", "site", "id", "expires" (epoch), "nest", "nested"
             (True when made on a site: the new site will be nested under it), "via"}. With via, the
             invitation's host and address are the relay's endpoint. The JSON holds
             the upstream's federation host name and address, the root CA's SHA-256 fingerprint, the
             organisation domain and base DN, the site name, the invitation id and its secret.
    Fails:   ValidationError "the federation endpoint is off: fabricctl federation enable"; site_name_problem's
             messages (not one label, or an organisation OU); "<name> is this site's own name"; "site <name> has joined already"; "this install
             has no CA yet"; "this site's CA cannot sign sites ..." (a site invited without --nest); "--nest N is more
             than this install's CA allows ..."; "no site <via> joined here ..."; ValidationError from
             load_secrets/save_secrets (OpenBao locked);
             OSError.
    Feeds:   run_federation_command (invite).
    Notes:   kept in fabric's secrets as federation_invitations[id] = {sha256 of the secret, site, expires,
             actor, nest}; an earlier open invitation for the same site is replaced and expired ones are dropped.
             The secret is shown once and never logged; audited as FED_INVITE."""
    if not v.get("federation_endpoint"):
        raise ValidationError("the federation endpoint is off: fabricctl federation enable")
    site_name = str(site_name).strip().lower()
    problem = site_name_problem(site_name, _org_ous(v))
    if problem:
        raise ValidationError(problem)
    if site_name == v.get("site_name"):
        raise ValidationError(f"{site_name} is this site's own name")
    root = ca_files(v)[0]
    if not os.path.exists(root):
        raise ValidationError("this install has no CA yet")
    nest = int(nest)
    cap = signing_capacity(v)
    if cap["max_nest"] is not None and cap["max_nest"] < 0:
        raise ValidationError("this site's CA cannot sign sites (path length 0): invite the new site from the "
                              "root site, or have this site invited again with --nest")
    if nest < 0 or (cap["max_nest"] is not None and nest > cap["max_nest"]):
        raise ValidationError(f"--nest {nest} is more than this install's CA allows (at most {cap['max_nest']})")
    now = int(now if now is not None else time.time())
    secret, inv_id = secrets.token_urlsafe(32), secrets.token_hex(6)
    expires = now + INVITE_TTL_SECONDS
    with federation_lock():
        sites = load_registry()["sites"]
        if site_name in sites:
            raise ValidationError(f"site {site_name} has joined already")
        relay = sites.get(via) if via else None
        if via and not relay:
            raise ValidationError(f"no site {via} joined here: a relay must be a site of this install")
        open_invites = {i: e for i, e in (load_secrets(v=v).get("federation_invitations") or {}).items()
                        if e.get("expires", 0) > now and e.get("site") != site_name}
        open_invites[inv_id] = {"sha256": hashlib.sha256(secret.encode()).hexdigest(), "site": site_name,
                                "expires": expires, "actor": actor, "nest": nest, "via": via}
        save_secrets({"federation_invitations": open_invites}, v=v)
    body = {"v": 1, "id": inv_id, "secret": secret, "site": site_name, "upstream": v.get("site_name"),
            "org_domain": v.get("org_domain") or v["domain"], "ldap_base_dn": v["ldap_base_dn"],
            "host": (relay.get("federation_host") or f"federation.{relay['domain']}") if relay else v["hostname_federation"],
            "address": relay["address"] if relay else v["host_ip"],
            "root_sha256": describe_cert(open(root).read())["sha256"], "expires": expires}
    if via:
        body["via"] = via
    text = INVITE_PREFIX + base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    write_audit(actor, "FED_INVITE", f"site={site_name} id={inv_id} nest={nest} via={via or '-'} expires={expires}",
                source)
    return {"invitation": text, "site": site_name, "id": inv_id, "expires": expires, "nest": nest,
            "nested": cap["as_parent"], "via": via}
