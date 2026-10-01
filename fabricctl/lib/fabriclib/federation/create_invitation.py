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


def create_invitation(v, actor, site_name, source="cli", now=None):
    """Purpose: On the upstream: a one-time invitation for a new site to join this fabric (design
             federation.md §4). Only a hash of its secret is kept.
    Inputs:  v — fabric vars: federation_endpoint (must be true), site_name (this site), domain, org_domain
             (default domain), ldap_base_dn, ldap_organizational_units, host_ip, hostname_federation,
             deploy_base_dir (the root certificate);
             actor — str (audit); site_name — the new site, SITE_NAME_RE, not this site's own, not joined
             already; source — default "cli"; now — epoch seconds, default time.time() (tests).
    Returns: {"invitation": "fabric-join-1.<base64url JSON>", "site", "id", "expires" (epoch)}. The JSON holds
             the upstream's federation host name and address, the root CA's SHA-256 fingerprint, the
             organisation domain and base DN, the site name, the invitation id and its secret.
    Fails:   ValidationError "the federation endpoint is off: fabricctl federation enable"; site_name_problem's
             messages (not one label, or an organisation OU); "<name> is this site's own name"; "site <name> has joined already"; "this install
             has no CA yet"; ValidationError from load_secrets/save_secrets (OpenBao locked); OSError.
    Feeds:   run_federation_command (invite).
    Notes:   kept in fabric's secrets as federation_invitations[id] = {sha256 of the secret, site, expires,
             actor}; an earlier open invitation for the same site is replaced and expired ones are dropped.
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
    now = int(now if now is not None else time.time())
    secret, inv_id = secrets.token_urlsafe(32), secrets.token_hex(6)
    expires = now + INVITE_TTL_SECONDS
    with federation_lock():
        if site_name in load_registry()["sites"]:
            raise ValidationError(f"site {site_name} has joined already")
        open_invites = {i: e for i, e in (load_secrets(v=v).get("federation_invitations") or {}).items()
                        if e.get("expires", 0) > now and e.get("site") != site_name}
        open_invites[inv_id] = {"sha256": hashlib.sha256(secret.encode()).hexdigest(), "site": site_name,
                                "expires": expires, "actor": actor}
        save_secrets({"federation_invitations": open_invites}, v=v)
    body = {"v": 1, "id": inv_id, "secret": secret, "site": site_name, "upstream": v.get("site_name"),
            "org_domain": v.get("org_domain") or v["domain"], "ldap_base_dn": v["ldap_base_dn"],
            "host": v["hostname_federation"],
            "address": v["host_ip"], "root_sha256": describe_cert(open(root).read())["sha256"], "expires": expires}
    text = INVITE_PREFIX + base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    write_audit(actor, "FED_INVITE", f"site={site_name} id={inv_id} expires={expires}", source)
    return {"invitation": text, "site": site_name, "id": inv_id, "expires": expires}
