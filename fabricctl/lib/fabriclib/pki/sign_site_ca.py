import datetime
import json
import os
import secrets
import shutil
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.constants import SITE_NAME_RE
from fabriclib.pki.common.artifacts_dir import artifacts_dir
from fabriclib.pki.common.ca_files import ca_files
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


def sign_site_ca(v, actor, site_name, csr, root_key="", root_password_file="", source="cli"):
    """Purpose: On the root site: sign a joining site's intermediate CA with this fabric's root key. The
             site made the key itself (make_site_ca_request); only the request travels.
    Inputs:  v — fabric vars: deploy_base_dir, service_users.step, image_stepca, site_name (this site),
             byoc, cert_intermediate_days (default 1095); actor — str (audit, ledger); site_name — the
             joining site, SITE_NAME_RE, not this site's own; csr — PEM/DER/base64 request whose only name is
             CN "<site_name> Intermediate CA" (step's copy of the CN as a DNS name is ignored); root_key, root_password_file — the root key and its password
             file, needed when this install's CA was brought in (byoc: its root key is not on this host);
             otherwise Step-CA's own secrets/root_ca_key and secrets/password; source — default "cli".
    Returns: {"cert": PEM of the site's intermediate CA, "root": PEM of the root, "info": describe_cert dict}.
             The certificate, from a fixed template: subject CN "<site_name> Intermediate CA" and no other
             names, CA:TRUE with path length 0 (signs leaves only), certificate and CRL signing, the request's
             key; valid cert_intermediate_days but never past the root's own expiry.
    Fails:   ValidationError "invalid site name: ..."; "<name> is this site's own name"; "cannot sign: ..."
             (signature, key strength, or a name other than the expected CN); "this install's root key is
             not on this host ..." (byoc without root_key) or "no such file: ..."; "the root CA expires in
             under 30 days"; "step-ca refused: ..." (wrong key or password); "refusing: ..." when the result
             is not a path-length-0 CA chaining to this root; OSError.
    Feeds:   the federation endpoint's join (M3), `fabricctl federation sign-csr` for a byoc root (M3).
    Notes:   ledger kind "site-ca"; audited as FED_SIGN_SITE_CA. Files given to step are copied into the
             artifacts directory under random names (0600, step user) and removed afterwards.
    """
    if not SITE_NAME_RE.match(str(site_name)):
        raise ValidationError(f"invalid site name: {site_name!r} (one host-name label: a-z, 0-9, -)")
    if site_name == v.get("site_name"):
        raise ValidationError(f"{site_name} is this site's own name")
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
    root_crt = ca_files(v)[0]
    if root_key or root_password_file:
        for p in (root_key, root_password_file):
            if not p or not os.path.isfile(p):
                raise ValidationError(f"no such file: {p or '(root key and its password file are both needed)'}")
    elif v.get("byoc"):
        raise ValidationError("this install's root key is not on this host (its CA was brought in): "
                              "give the root key and its password file to sign a site's CA")
    else:
        root_key = os.path.join(data, "secrets", "root_ca_key")
        root_password_file = os.path.join(data, "secrets", "password")
        if not os.path.isfile(root_key):
            raise ValidationError("this install's root key is not on this host: give the root key and its "
                                  "password file to sign a site's CA")
    root_pem = open(root_crt).read()
    left = _hours_left(describe_cert(root_pem)["not_after"])
    if left < MIN_ROOT_DAYS_LEFT * 24:
        raise ValidationError("the root CA expires in under 30 days: renew it before adding sites")
    hours = min(int(v.get("cert_intermediate_days", 1095)) * 24, left - 1)

    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    art, tag = artifacts_dir(v), secrets.token_hex(8)
    staged = {"csr": f"site-{tag}.csr", "key": f"site-{tag}.key", "pw": f"site-{tag}.pw", "tpl": f"site-{tag}.tpl"}
    template = {"subject": {"commonName": want}, "keyUsage": ["certSign", "crlSign"],
                "basicConstraints": {"isCA": True, "maxPathLen": 0}}
    try:
        with open(os.path.join(art, staged["tpl"]), "x") as f:
            json.dump(template, f)
        os.chown(os.path.join(art, staged["tpl"]), uid, gid)
        with open(os.path.join(art, staged["csr"]), "x") as f:
            f.write(req["pem"])
        os.chmod(os.path.join(art, staged["csr"]), 0o600)
        os.chown(os.path.join(art, staged["csr"]), uid, gid)
        _stage(root_key, os.path.join(art, staged["key"]), uid, gid)
        _stage(root_password_file, os.path.join(art, staged["pw"]), uid, gid)
        out = run_step(v, ["certificate", "sign", f"/home/step/artifacts/{staged['csr']}",
                           "/home/step/certs/root_ca.crt", f"/home/step/artifacts/{staged['key']}",
                           "--template", f"/home/step/artifacts/{staged['tpl']}", "--not-after", f"{hours}h",
                           "--password-file", f"/home/step/artifacts/{staged['pw']}"])
    finally:
        for name in staged.values():
            if os.path.exists(os.path.join(art, name)):
                os.remove(os.path.join(art, name))

    cert = to_pem(out, "cert")[0]
    text = subprocess.run(["openssl", "x509", "-noout", "-text"], input=cert, capture_output=True, text=True).stdout
    if "CA:TRUE, pathlen:0" not in text:
        raise ValidationError("refusing: the signed certificate is not a path-length-0 CA")
    verify = subprocess.run(["openssl", "verify", "-CAfile", root_crt], input=cert, capture_output=True, text=True)
    if verify.returncode != 0:
        raise ValidationError("refusing: the signed certificate does not chain to this root (wrong root key?)")
    info = describe_cert(cert)
    record_issued(actor, "site-ca", dict(info, device=site_name), source)
    write_audit(actor, "FED_SIGN_SITE_CA", f"site={site_name} serial={info['serial']} "
                                          f"not_after={info['not_after']}", source)
    return {"cert": cert, "root": root_pem, "info": info}
