from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.common.valid_days import DEFAULT_MAX_DAYS


def ca_summary(v):
    """The CA certificates (subject, validity, fingerprint), where devices
    fetch them, and the signing limits the web UI enforces."""
    out = {"domain": v.get("domain", ""), "certs_url": f"http://{v.get('hostname_certs', '')}/", "max_days": int(v.get("pki_manual_max_days")
                                                                                 or DEFAULT_MAX_DAYS)}
    for label, path in zip(("root", "intermediate"), ca_files(v)):
        with open(path) as f:
            out[label] = describe_cert(to_pem(f.read(), "cert")[0])
    return out
