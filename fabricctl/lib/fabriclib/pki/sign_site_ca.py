import datetime
import json
import os
import secrets
import shutil
import subprocess
import tempfile

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.constants import SITE_NAME_RE
from fabriclib.pki.common.artifacts_dir import artifacts_dir
from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.ca_parents_pem import ca_parents_pem
from fabriclib.pki.common.ca_path_len import ca_path_len
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.record_issued import record_issued
from fabriclib.pki.common.run_step import run_step
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.describe_csr import describe_csr

MIN_ROOT_DAYS_LEFT = 30


def _hours_left(not_after):
    """Purpose: whole hours from now until an openssl notAfter date.
    Inputs:  not_after — e.g. "Sep 30 12:00:00 2036 GMT".
    Returns: int (negative once passed).
    Fails:   ValueError for another date format.
    Feeds:   sign_site_ca (a site's CA never outlives the root)."""
    end = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
    return int((end - datetime.datetime.now(datetime.timezone.utc)).total_seconds() // 3600)


def _stage(src, dst, uid, gid):
    """Purpose: copy a file into the step user's artifacts directory for one signing, 0600.
    Inputs:  src, dst — paths; uid, gid — the step user.
    Returns: None.
    Fails:   OSError.
    Feeds:   sign_site_ca (the CSR, and a root key and password brought in for a byoc root)."""
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out, open(src, "rb") as f:
        shutil.copyfileobj(f, out)
    os.chown(dst, uid, gid)


def sign_site_ca(v, actor, site_name, csr, root_key="", root_password_file="", source="cli", nest=0,
                 as_parent=False):
    """Purpose: Sign a joining site's intermediate CA (design federation.md §6): with the root key (a flat site,
             or one allowed to hold nested sites), or — as_parent — with this site's own CA, for a site nested
             under this one. The joining site made the key itself (make_site_ca_request); only the request
             travels.
    Inputs:  v — fabric vars: deploy_base_dir, service_users.step, image_stepca, site_name (this site),
             byoc, cert_intermediate_days (default 1095); actor — str (audit, ledger); site_name — the
             joining site, SITE_NAME_RE, not this site's own; csr — PEM/DER/base64 request whose only name is
             CN "<site_name> Intermediate CA" (step's copy of the CN as a DNS name is ignored); root_key,
             root_password_file — the root key and its password file, needed when this install's CA was
             brought in (byoc: its root key is not on this host); otherwise Step-CA's own secrets/root_ca_key
             and secrets/password; source — default "cli"; nest — the new CA's path length: how many levels of
             sites it may hold below it, default 0; as_parent — sign with this site's intermediate
             (secrets/intermediate_ca_key) instead of the root key.
    Returns: {"cert": PEM of the site's intermediate CA, "root": PEM of the root, "chain": PEM of the CAs between
             the new CA and the root ("" when the root signed; this site's CA and its parents when as_parent),
             "info": describe_cert dict}. The certificate, from a fixed template: subject CN
             "<site_name> Intermediate CA" and no other names, CA:TRUE with path length `nest`, certificate and
             CRL signing, the request's key; valid cert_intermediate_days but never past the root's own expiry.
    Fails:   ValidationError "invalid site name: ..."; "<name> is this site's own name"; "cannot sign: ..."
             (signature, key strength, or a name other than the expected CN); "nest must be 0 or more"; "this
             site's CA cannot hold sites below it" / "the root allows ... levels" / "this site's CA allows ..."
             when nest is more than the signer's path length permits; "this install's root key is not on this
             host ..." (byoc without root_key) or "no such file: ..."; "the root CA expires in under 30 days";
             "step-ca refused: ..." (wrong key or password); "refusing: ..." when the result is not a CA of
             path length `nest` chaining to this root; OSError.
    Feeds:   accept_join (the federation endpoint's join), `fabricctl federation sign-csr` for a byoc root.
    Notes:   ledger kind "site-ca"; audited as FED_SIGN_SITE_CA. Files given to step are copied into the
             artifacts directory under random names (0600, step user) and removed afterwards.
    """
    if not SITE_NAME_RE.match(str(site_name)):
        raise ValidationError(f"invalid site name: {site_name!r} (one host-name label: a-z, 0-9, -)")
    if site_name == v.get("site_name"):
        raise ValidationError(f"{site_name} is this site's own name")
    nest = int(nest)
    if nest < 0:
        raise ValidationError("nest must be 0 or more")
    req = describe_csr(csr)
    want = f"{site_name} Intermediate CA"
    # step puts the CN in a DNS name too: that one is ignored like the rest of the request's extensions
    problems = [p for p in req["problems"]
                if not p.startswith("the common name") and p != f"unsupported or malformed name: DNS:{want}"]
    if req["cn"] != want or req["sans"]:
        problems.append(f"a site's request names only CN={want!r} (got CN={req['cn']!r}, SANs {req['sans']})")
    if problems:
        raise ValidationError("cannot sign: " + "; ".join(problems))

    data = os.path.join(v["deploy_base_dir"], "stepca", "data")
    root_crt, ica_crt = ca_files(v)
    root_pem = open(root_crt).read()
    if as_parent:
        issuer_crt = "/home/step/certs/intermediate_ca.crt"
        key, password_file = os.path.join(data, "secrets", "intermediate_ca_key"), os.path.join(data, "secrets", "password")
        issuer_pem = open(ica_crt).read()
        chain = issuer_pem.strip() + "\n" + ca_parents_pem(v)
        depth = ca_path_len(issuer_pem)
        if depth is not None and depth < 1:
            raise ValidationError("this site's CA cannot hold sites below it (path length 0): invite the site "
                                  "from the root, or have this site invited again with --nest")
        if depth is not None and nest > depth - 1:
            raise ValidationError(f"this site's CA allows {depth - 1} more level(s) below a site it signs "
                                  f"(asked: --nest {nest})")
    else:
        issuer_crt, chain = "/home/step/certs/root_ca.crt", ""
        depth = ca_path_len(root_pem)
        if depth is not None and nest > depth - 1:
            raise ValidationError(f"the root allows {max(depth - 1, 0)} level(s) of sites below a site "
                                  f"(asked: --nest {nest}); deeper nesting needs a root made with a larger "
                                  "ca_nest_depth")
        key, password_file = root_key, root_password_file
        if key or password_file:
            for p in (key, password_file):
                if not p or not os.path.isfile(p):
                    raise ValidationError(f"no such file: {p or '(root key and its password file are both needed)'}")
        elif v.get("byoc"):
            raise ValidationError("this install's root key is not on this host (its CA was brought in): "
                                  "give the root key and its password file to sign a site's CA")
        else:
            key = os.path.join(data, "secrets", "root_ca_key")
            password_file = os.path.join(data, "secrets", "password")
            if not os.path.isfile(key):
                raise ValidationError("this install's root key is not on this host: give the root key and its "
                                      "password file to sign a site's CA")
    left = _hours_left(describe_cert(root_pem)["not_after"])
    if left < MIN_ROOT_DAYS_LEFT * 24:
        raise ValidationError("the root CA expires in under 30 days: renew it before adding sites")
    hours = min(int(v.get("cert_intermediate_days", 1095)) * 24, left - 1)
    if as_parent:
        hours = min(hours, _hours_left(describe_cert(issuer_pem)["not_after"]) - 1)

    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    art, tag = artifacts_dir(v), secrets.token_hex(8)
    staged = {"csr": f"site-{tag}.csr", "key": f"site-{tag}.key", "pw": f"site-{tag}.pw", "tpl": f"site-{tag}.tpl"}
    template = {"subject": {"commonName": want}, "keyUsage": ["certSign", "crlSign"],
                "basicConstraints": {"isCA": True, "maxPathLen": nest}}
    try:
        with open(os.path.join(art, staged["tpl"]), "x") as f:
            json.dump(template, f)
        os.chown(os.path.join(art, staged["tpl"]), uid, gid)
        with open(os.path.join(art, staged["csr"]), "x") as f:
            f.write(req["pem"])
        os.chmod(os.path.join(art, staged["csr"]), 0o600)
        os.chown(os.path.join(art, staged["csr"]), uid, gid)
        _stage(key, os.path.join(art, staged["key"]), uid, gid)
        _stage(password_file, os.path.join(art, staged["pw"]), uid, gid)
        out = run_step(v, ["certificate", "sign", f"/home/step/artifacts/{staged['csr']}",
                           issuer_crt, f"/home/step/artifacts/{staged['key']}",
                           "--template", f"/home/step/artifacts/{staged['tpl']}", "--not-after", f"{hours}h",
                           "--password-file", f"/home/step/artifacts/{staged['pw']}"])
    finally:
        for name in staged.values():
            if os.path.exists(os.path.join(art, name)):
                os.remove(os.path.join(art, name))

    cert = to_pem(out, "cert")[0]
    if ca_path_len(cert) != nest:
        raise ValidationError(f"refusing: the signed certificate is not a CA of path length {nest}")
    with tempfile.NamedTemporaryFile("w", suffix=".pem") as untrusted:
        untrusted.write(chain)
        untrusted.flush()
        args = ["openssl", "verify", "-CAfile", root_crt] + (["-untrusted", untrusted.name] if chain.strip() else [])
        verify = subprocess.run(args, input=cert, capture_output=True, text=True)
    if verify.returncode != 0:
        raise ValidationError("refusing: the signed certificate does not chain to this root (wrong key?)")
    info = describe_cert(cert)
    record_issued(actor, "site-ca", dict(info, device=site_name), source)
    write_audit(actor, "FED_SIGN_SITE_CA", f"site={site_name} serial={info['serial']} nest={nest} "
                                          f"signer={'site' if as_parent else 'root'} not_after={info['not_after']}",
                source)
    return {"cert": cert, "root": root_pem, "chain": chain if as_parent else "", "info": info}
