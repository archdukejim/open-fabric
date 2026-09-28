import filecmp
import json
import os
import shutil
import subprocess
import tempfile

TRUST_DIR = "/usr/local/share/ca-certificates"


def _openssl(*args, data=None):
    return subprocess.run(["openssl", *args], input=data, capture_output=True, check=True,
                          text=isinstance(data, str)).stdout


def _info(pem_path):
    """Subject, issuer, validity and fingerprints of one certificate."""
    out = _openssl("x509", "-in", pem_path, "-noout", "-subject", "-issuer", "-startdate", "-enddate",
                   "-nameopt", "RFC2253", "-fingerprint", "-sha256").decode()
    sha1 = _openssl("x509", "-in", pem_path, "-noout", "-fingerprint", "-sha1").decode()
    vals = {}
    for line in (out + sha1).splitlines():
        key, _, value = line.partition("=")
        vals[key.strip().lower()] = value.strip()
    return {"subject": vals.get("subject", ""), "issuer": vals.get("issuer", ""),
            "not_before": vals.get("notbefore", ""), "not_after": vals.get("notafter", ""),
            "sha256": vals.get("sha256 fingerprint", ""), "sha1": vals.get("sha1 fingerprint", "")}


def _write_if_changed(path, data, uid, gid):
    mode = "wb" if isinstance(data, bytes) else "w"
    old = open(path, "rb" if mode == "wb" else "r").read() if os.path.exists(path) else None
    changed = old != data
    if changed:
        with open(path, mode) as f:
            f.write(data)
    os.chown(path, uid, gid)
    os.chmod(path, 0o644)
    return changed


def publish_ca_certs(certs_dir, www_dir, uid, gid, trust_prefix):
    """Publish the fabric root and intermediate CA certificates for every kind
    of system into www_dir (served at certs.<domain>) and trust them on this
    host. Idempotent; returns True if anything changed.

      root-ca.crt / intermediate-ca.crt   PEM   Linux, macOS, iOS, Android
      root-ca.cer / intermediate-ca.cer   DER   Windows
      root-ca.pem / intermediate-ca.pem   PEM   shown as text (paste into devices)
      root-ca.der / intermediate-ca.der   DER   devices that want binary DER
      ca-chain.pem                        PEM   intermediate + root bundle
      ca-chain.p7b                        PKCS#7 (DER) root + intermediate
      ca-certs.json                       subject, validity, SHA-256/SHA-1 fingerprints

    certs_dir holds Step-CA's root_ca.crt and intermediate_ca.crt (the latter may
    carry the root too, as with a bring-your-own chain: only its first
    certificate is the intermediate)."""
    os.makedirs(www_dir, exist_ok=True)
    changed = False
    info = {}
    with tempfile.TemporaryDirectory() as tmp:
        pems = {}
        for name, src in (("root-ca", "root_ca.crt"), ("intermediate-ca", "intermediate_ca.crt")):
            pem = _openssl("x509", "-in", os.path.join(certs_dir, src)).decode()     # first cert only
            der = _openssl("x509", "-in", os.path.join(certs_dir, src), "-outform", "DER")
            pems[name] = pem
            for ext, data in (("crt", pem), ("pem", pem), ("cer", der), ("der", der)):
                changed |= _write_if_changed(os.path.join(www_dir, f"{name}.{ext}"), data, uid, gid)
            tmp_pem = os.path.join(tmp, f"{name}.pem")
            with open(tmp_pem, "w") as f:
                f.write(pem)
            info[name] = _info(tmp_pem)
        chain = pems["intermediate-ca"] + pems["root-ca"]
        changed |= _write_if_changed(os.path.join(www_dir, "ca-chain.pem"), chain, uid, gid)
        chain_path = os.path.join(tmp, "chain.pem")
        with open(chain_path, "w") as f:
            f.write(chain)
        p7b = _openssl("crl2pkcs7", "-nocrl", "-certfile", chain_path, "-outform", "DER")
        changed |= _write_if_changed(os.path.join(www_dir, "ca-chain.p7b"), p7b, uid, gid)
        changed |= _write_if_changed(os.path.join(www_dir, "ca-certs.json"),
                                     json.dumps(info, indent=2) + "\n", uid, gid)

        # This host trusts its own CA (system store: curl, python, apt, docker ...).
        trust_changed = False
        for name in ("root-ca", "intermediate-ca"):
            dst = os.path.join(TRUST_DIR, f"{trust_prefix}-{name}.crt")
            src = os.path.join(www_dir, f"{name}.crt")
            if not (os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False)):
                shutil.copy2(src, dst)
                os.chmod(dst, 0o644)
                trust_changed = True
        if trust_changed:
            subprocess.run(["update-ca-certificates", "--fresh"], check=True, capture_output=True)
    return changed or trust_changed
