import base64
import os
import secrets
import tempfile
import threading

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.directory.link_device_cert import link_device_cert
from fabriclib.directory.require_device import require_device
from fabriclib.pki.common.ca_chain_pem import ca_chain_pem
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.openssl import openssl
from fabriclib.pki.common.record_issued import record_issued
from fabriclib.pki.common.safe_name import safe_name
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.common.valid_days import valid_days
from fabriclib.pki.common.valid_san import valid_san
from fabriclib.pki.export_p12 import export_p12
from fabriclib.pki.mint_offline_cert import mint_offline_cert

# label -> (kty, RSA size, curve)
KEY_TYPES = {"RSA-2048": ("RSA", 2048, None), "RSA-3072": ("RSA", 3072, None), "RSA-4096": ("RSA", 4096, None),
             "EC-P256": ("EC", None, "P-256"), "EC-P384": ("EC", None, "P-384")}
_lock = threading.Lock()                    # artifact file names derive from the CN


def issue_key_pair(v, actor, cn, sans=(), key_type="RSA-2048", days=365, device="", source="web"):
    """Purpose: Generate a private key and a leaf certificate for a device that cannot make its own CSR;
             the key is handed out once and not kept on this host.
    Inputs:  v — fabric vars; actor — str (audit, ledger, device link); cn — host name, IP or e-mail
             (valid_san); sans — iterable of str, blanks dropped, each valid_san; key_type — a KEY_TYPES
             label: "RSA-2048" (default), "RSA-3072", "RSA-4096", "EC-P256", "EC-P384"; days — 1 ..
             pki_manual_max_days (valid_days), default 365; device — optional directory device to link,
             checked first (require_device); source — default "web".
    Returns: {"name", "cert", "chain" (intermediate + root), "fullchain", "key" (PEM), "der_b64", "p12_b64",
             "p12_password", "info": describe_cert dict, "device"}.
    Fails:   ValidationError "the name ... is not a host name, IP address or e-mail address"; "invalid
             alternative names: ..."; "key type must be one of ..."; valid_days' messages; "no device
             named ..." (require_device); "invalid certificate name: ..." from mint_offline_cert (an IPv6
             or e-mail CN with + or % passes valid_san but not CN_RE); "step-ca refused: ..." (run_step);
             link_device_cert / run_op errors (raised after issuing); CalledProcessError from
             export_p12; OSError.
    Feeds:   agent route POST /v1/pki/issue -> webui agentclient.issue_key_pair -> PKI page.
    Notes:   a module lock serialises minting because artifact file names derive from the CN; the
             artifacts are deleted right after reading. Recorded in the ledger (record_issued, kind
             "keypair") and audited as PKI_ISSUE.
    """
    cn = str(cn).strip()
    if not valid_san(cn):
        raise ValidationError(f"the name {cn!r} is not a host name, IP address or e-mail address")
    sans = [s.strip() for s in sans if s.strip()]
    bad = [s for s in sans if not valid_san(s)]
    if bad:
        raise ValidationError(f"invalid alternative names: {', '.join(bad)}")
    if key_type not in KEY_TYPES:
        raise ValidationError(f"key type must be one of {', '.join(KEY_TYPES)}")
    days = valid_days(v, days)
    if device:
        require_device(v, device)
    kty, size, crv = KEY_TYPES[key_type]
    with _lock:
        crt_path, key_path = mint_offline_cert(v, cn, sans, days=days, kty=kty, size=size or 2048, crv=crv)
        try:
            with open(crt_path) as f:
                cert = to_pem(f.read(), "cert")[0]
            with open(key_path) as f:
                key = f.read()
        finally:
            for path in (crt_path, key_path):
                if os.path.exists(path):
                    os.remove(path)
    chain = ca_chain_pem(v)
    password = secrets.token_urlsafe(15)
    with tempfile.TemporaryDirectory(prefix="fabric-issue-") as tmp:          # 0700
        files = {}
        for label, body in (("crt", cert), ("key", key), ("chain", chain)):
            files[label] = os.path.join(tmp, label)
            fd = os.open(files[label], os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(body)
        p12 = os.path.join(tmp, "out.p12")
        export_p12(files["crt"], files["key"], [files["chain"]], cn, password, p12)
        with open(p12, "rb") as f:
            p12_b64 = base64.b64encode(f.read()).decode()
    info = describe_cert(cert)
    if device:
        link_device_cert(v, actor, device, info["sha256"], source=source)
    record_issued(actor, "keypair", dict(info, device=device), source)
    write_audit(actor, "PKI_ISSUE", f"subject={info['subject']} sans={','.join(info['sans'])} key={key_type} "
                                    f"serial={info['serial']} days={days} (key handed out, not kept)", source)
    return {"name": safe_name(cn), "cert": cert, "chain": chain, "fullchain": cert + chain, "key": key,
            "der_b64": base64.b64encode(openssl("x509", "-outform", "DER", data=cert.encode())).decode(),
            "p12_b64": p12_b64, "p12_password": password, "info": info, "device": device}
