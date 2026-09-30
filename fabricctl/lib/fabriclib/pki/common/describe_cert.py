import re

from fabriclib.pki.common.openssl import openssl


def describe_cert(pem):
    """Subject, issuer, names, key, validity, usages and fingerprint of one
    PEM certificate, as a dict for pages and the issued-certificate ledger."""
    out = openssl("x509", "-noout", "-subject", "-issuer", "-serial", "-startdate", "-enddate",
                  "-fingerprint", "-sha256", "-nameopt", "RFC2253", data=pem)
    vals = {}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        vals[k.strip().lower()] = v.strip()
    text = openssl("x509", "-noout", "-text", data=pem)
    san = re.search(r"Subject Alternative Name:.*?\n\s*(.+)", text)
    eku = re.search(r"Extended Key Usage:.*?\n\s*(.+)", text)
    key = re.search(r"Public Key Algorithm: (\S+).*?(?:Public-Key: \((\d+) bit\)|ASN1 OID: (\S+))", text, re.S)
    alg = {"rsaEncryption": "RSA", "id-ecPublicKey": "EC"}.get(key.group(1), key.group(1)) if key else "?"
    size = (key.group(2) or key.group(3) or "") if key else ""
    return {"subject": vals.get("subject", ""), "issuer": vals.get("issuer", ""),
            "serial": vals.get("serial", ""), "not_before": vals.get("notbefore", ""),
            "not_after": vals.get("notafter", ""), "sha256": vals.get("sha256 fingerprint", ""),
            "sans": [s.strip() for s in san.group(1).split(",")] if san else [],
            "usage": eku.group(1).strip() if eku else "", "key": f"{alg} {size}".strip(),
            "is_ca": "CA:TRUE" in text}
