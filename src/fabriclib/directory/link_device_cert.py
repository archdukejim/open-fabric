from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets
from fabriclib.directory.constants import DEVICE_NAME_RE, FINGERPRINT_RE


def link_device_cert(v, actor, name, fingerprint, link=True, source="web"):
    """Purpose: Record (link) or forget a certificate's SHA-256 fingerprint on a device, so 802.1X EAP-TLS
             can tell which device a certificate belongs to.
    Inputs:  v — fabric vars; actor — str, for the audit; name — device name (DEVICE_NAME_RE);
             fingerprint — SHA-256 as 32 colon-separated hex pairs (upper-cased); link — True adds, False
             removes; source — default "web".
    Returns: None. Idempotent: adding a present or removing an absent fingerprint is not an error.
    Fails:   ValidationError "invalid device name: ..."; "not a SHA-256 fingerprint"; "no such entry" (no
             such device);
             run_op's errors (the directory unreachable, or refusing: e.g. another site's object).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/devices/<name>/certs) -> webui
             agentclient.link_device_cert;
             pki/issue_key_pair, pki/sign_csr.
    Notes:   audited as DEVICE_CERT_LINK or DEVICE_CERT_UNLINK.
    """
    fp = str(fingerprint).strip().upper()
    if not DEVICE_NAME_RE.match(str(name)):
        raise ValidationError(f"invalid device name: {name!r}")
    if not FINGERPRINT_RE.match(fp):
        raise ValidationError("not a SHA-256 fingerprint")
    run_op(v, load_secrets(), "link_device_cert", {"name": name, "fingerprint": fp, "link": bool(link)})
    write_audit(actor, "DEVICE_CERT_LINK" if link else "DEVICE_CERT_UNLINK", f"device={name} sha256={fp}", source)
