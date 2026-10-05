import base64
import os
import secrets

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.directory.link_device_cert import link_device_cert
from fabriclib.directory.require_device import require_device
from fabriclib.pki.common.artifacts_dir import artifacts_dir
from fabriclib.pki.common.ca_chain_pem import ca_chain_pem
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.openssl import openssl
from fabriclib.pki.common.record_issued import record_issued
from fabriclib.pki.common.run_step import run_step
from fabriclib.pki.common.safe_name import safe_name
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.common.valid_days import valid_days
from fabriclib.pki.describe_csr import describe_csr


def sign_csr(v, actor, csr, days, device="", source="web"):
    """Purpose: Sign a device's certificate signing request with the Step-CA intermediate as a leaf
             certificate; the private key never leaves the device.
    Inputs:  v — fabric vars; actor — str (audit, ledger, device link); csr — PEM, DER or base64
             (describe_csr); days — 1 .. pki_manual_max_days (valid_days); device — optional directory
             device to link, checked first (require_device); source — default "web".
    Returns: {"name", "cert", "chain" (intermediate + root), "fullchain", "der_b64", "info": describe_cert
             dict, "device"}.
    Fails:   ValidationError "cannot sign: <problems>"; describe_csr's messages; valid_days' messages; "no
             device named ..."; "step-ca refused: ..." (run_step); "refusing: the signed certificate would
             be a CA"; link_device_cert / run_dirsrv errors (raised after signing); OSError.
    Feeds:   agent route POST /v1/pki/sign -> webui agentclient.sign_csr -> PKI page.
    Notes:   the leaf template sets serverAuth + clientAuth, the CSR's names and fabric's subject defaults;
             the CSR's own extensions are ignored. The CSR goes to a random-named artifact file (O_EXCL,
             0640, step user) that is removed afterwards. Ledger kind "csr"; audited as PKI_SIGN_CSR.
    """
    req = describe_csr(csr)
    if req["problems"]:
        raise ValidationError("cannot sign: " + "; ".join(req["problems"]))
    days = valid_days(v, days)
    if device:
        require_device(v, device)
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    name = f"csr-{secrets.token_hex(8)}.csr"
    path = os.path.join(artifacts_dir(v), name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(fd, "w") as f:
        f.write(req["pem"])
    os.chown(path, uid, gid)
    try:
        out = run_step(v, ["certificate", "sign", f"/home/step/artifacts/{name}",
                           "/home/step/certs/intermediate_ca.crt", "/home/step/secrets/intermediate_ca_key",
                           "--password-file", "/home/step/secrets/password",
                           "--template", "/home/step/templates/certs/leaf.tpl",
                           "--not-after", f"{days * 24}h"])
    finally:
        os.remove(path)
    cert = to_pem(out, "cert")[0]
    info = describe_cert(cert)
    if info["is_ca"]:                       # the leaf template never sets CA:TRUE; belt and braces
        raise ValidationError("refusing: the signed certificate would be a CA")
    chain = ca_chain_pem(v)
    if device:
        link_device_cert(v, actor, device, info["sha256"], source=source)
    record_issued(actor, "csr", dict(info, device=device), source)
    write_audit(actor, "PKI_SIGN_CSR", f"subject={info['subject']} sans={','.join(info['sans'])} "
                                       f"serial={info['serial']} days={days}", source)
    return {"name": safe_name(req["cn"] or req["sans"][0]), "cert": cert, "chain": chain, "fullchain": cert + chain,
            "der_b64": base64.b64encode(openssl("x509", "-outform", "DER", data=cert.encode())).decode(),
            "info": info, "device": device}
