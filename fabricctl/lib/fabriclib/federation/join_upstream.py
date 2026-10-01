import datetime
import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.paths import AUDIT_FILE, FEDERATION_FILE, FEDERATION_LOCK_FILE
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.federation_lock import federation_lock
from fabriclib.federation.common.fetch_pinned_root import fetch_pinned_root
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.common.post_upstream import post_upstream
from fabriclib.federation.common.save_registry import save_registry
from fabriclib.federation.constants import DOMAIN_RE
from fabriclib.federation.decode_invitation import decode_invitation
from fabriclib.pki.make_site_ca_request import make_site_ca_request
from fabriclib.pki.stage_site_ca import stage_site_ca

ORG_KEYS = ("friendly_name", "cert_country", "cert_province", "cert_city", "cert_org", "cert_ou")


def join_upstream(v, invitation, password, work_dir, domain, address, config_dir=None, audit_path=None,
                  http_port=80, https_port=443):
    """Purpose: On a node being set up with `--join`: join the upstream that made the invitation (design
             federation.md §4 step 2): make this site's CA key and request, fetch and pin the upstream's root,
             send the join over TLS verified against that root, check and stage the signed intermediate, and
             record the upstream.
    Inputs:  v — fabric vars: service_users.step, image_stepca (make_site_ca_request); invitation — the
             invitation text (decode_invitation); password — this site's ca_password (encrypts its CA key);
             work_dir — where the site CA key, request and certificates are kept; domain — this site's own
             domain (DOMAIN_RE); address — this host's IP (host_ip); config_dir — the install's config folder
             for federation.yaml and its lock (default: next to this code — setup runs from the package, so it
             passes <base>/fabric/config); audit_path — default AUDIT_FILE; http_port, https_port — the
             upstream's ports, default 80 and 443 (tests).
    Returns: {"vars": settings for this install — byoc, ca_crt_path, ica_crt_path, ica_key_path (stage_site_ca),
             site_name, org_domain and the organisation's friendly_name / cert_* —, "upstream": {"site_name",
             "domain", "host", "address"}, "joined": True if this call joined, False if an earlier run had}.
    Fails:   ValidationError from decode_invitation, make_site_ca_request, fetch_pinned_root, post_upstream ("the
             upstream refused: ..."), stage_site_ca; "this site's domain is not valid"; "the upstream answered
             with a different root"; "this node already joined <upstream>, not the invitation's ..."; OSError.
    Feeds:   setup step `join` (fabriclib/setup/join_federation.py).
    Notes:   idempotent: once joined (an upstream recorded and the staged files present) a re-run returns the
             same settings without contacting the upstream, so setup can be repeated after a later failure.
             Audited as FED_JOINED."""
    inv = decode_invitation(invitation)
    domain = str(domain).strip().lower().rstrip(".")
    if not DOMAIN_RE.match(domain):
        raise ValidationError(f"this site's domain is not valid: {domain!r}")
    staged_files = [os.path.join(work_dir, n) for n in ("root_ca.crt", "site_ca.crt", "site_ca_key")]
    reg_path = os.path.join(config_dir, "federation.yaml") if config_dir else FEDERATION_FILE
    lock_path = os.path.join(config_dir, ".federation.lock") if config_dir else FEDERATION_LOCK_FILE
    registry = load_registry(reg_path)
    if registry["upstream"]:
        up = registry["upstream"]
        if up.get("site_name") != inv["upstream"] or up.get("site") != inv["site"]:
            raise ValidationError(f"this node already joined {up.get('site_name')} as {up.get('site')}, "
                                  f"not the invitation's {inv['upstream']} as {inv['site']}")
        if all(os.path.exists(p) for p in staged_files):
            return {"vars": _vars(inv, up, work_dir), "upstream": {k: up.get(k) for k in
                                                                   ("site_name", "domain", "host", "address")},
                    "joined": False}

    req = make_site_ca_request(v, inv["site"], password, work_dir)
    root = fetch_pinned_root(inv["address"], inv["root_sha256"], port=http_port)
    answer = post_upstream(inv["address"], inv["host"], root, "/v1/join",
                           {"id": inv["id"], "secret": inv["secret"], "site": inv["site"], "csr": req["csr"],
                            "domain": domain, "address": address}, port=https_port)
    if not isinstance(answer, dict) or answer.get("root", "").strip() != root.strip():
        raise ValidationError("the upstream answered with a different root")
    stage_site_ca(work_dir, answer.get("cert", ""), answer["root"], root_sha256=inv["root_sha256"])
    org = answer.get("org") or {}
    up = {**(answer.get("upstream") or {}), "site": inv["site"], "org_domain": org.get("org_domain") or inv["org_domain"],
          "root_sha256": inv["root_sha256"], "joined": datetime.datetime.now().isoformat(timespec="seconds"),
          "org": {k: org[k] for k in ORG_KEYS if org.get(k)}}
    with federation_lock(lock_path):
        registry = load_registry(reg_path)
        registry["upstream"] = up
        save_registry(registry, reg_path)
    write_audit("root", "FED_JOINED", f"upstream={up.get('site_name')} site={inv['site']} domain={domain}", "cli",
                path=audit_path or AUDIT_FILE)
    return {"vars": _vars(inv, up, work_dir), "upstream": {k: up.get(k) for k in ("site_name", "domain", "host", "address")},
            "joined": True}


def _vars(inv, up, work_dir):
    """Purpose: the settings a joined site is rendered with, from the invitation and the recorded upstream.
    Inputs:  inv — decode_invitation's dict; up — the registry's upstream record; work_dir — the staged files.
    Returns: dict: byoc True, ca_crt_path, ica_crt_path, ica_key_path, site_name, org_domain and the
             organisation's settings (friendly_name, cert_*).
    Fails:   never.
    Feeds:   join_upstream (both the first join and a re-run)."""
    return {"byoc": True, "ca_crt_path": os.path.join(work_dir, "root_ca.crt"),
            "ica_crt_path": os.path.join(work_dir, "site_ca.crt"), "ica_key_path": os.path.join(work_dir, "site_ca_key"),
            "site_name": inv["site"], "org_domain": up.get("org_domain") or inv["org_domain"], **(up.get("org") or {})}
