import os
import re

from fabriclib.common.errors import ValidationError
from fabriclib.pki.common.artifacts_dir import artifacts_dir
from fabriclib.pki.common.run_step import run_step

CN_RE = re.compile(r"^[A-Za-z0-9*][A-Za-z0-9._@*-]{0,252}$")


def mint_offline_cert(v, cn, sans=(), days=365, kty="RSA", size=4096, is_ca=False, path_len=0, crv=None):
    """Purpose: Sign a certificate directly with the Step-CA intermediate key, whether or not step-ca is
             running.
    Inputs:  v — fabric vars (artifacts_dir, run_step); cn — ^[A-Za-z0-9*][A-Za-z0-9._@*-]{0,252}$;
             sans — extra names (leaf only; cn is always included); days — validity, default 365 (no cap
             here); kty — "RSA" | "EC" | "OKP"; size — RSA bits, default 4096; is_ca — issue a subordinate
             CA (subca template, pathLen=path_len) instead of a leaf (leaf template); crv — curve for EC /
             OKP (P-256, P-384, Ed25519), step's default when None.
    Returns: (crt_path, key_path) in stepca/data/artifacts, named after cn with ". / space @ *" as "-";
             the crt carries the chain (--bundle), the key is unencrypted. The caller moves or deletes both.
    Fails:   ValidationError "invalid certificate name: ..."; run_step's "step-ca refused: ..."; ValueError
             if days / size / path_len are not numbers; KeyError / OSError from artifacts_dir.
    Feeds:   issue_client_cert, issue_key_pair, mint_extra_cert.
    Notes:   the intermediate key's password is a file path inside the container, never a value on argv.
    """
    if not CN_RE.match(cn):
        raise ValidationError(f"invalid certificate name: {cn!r}")
    artifacts = artifacts_dir(v)
    name = re.sub(r"[./ @*]", "-", cn)
    cmd = ["certificate", "create", cn, f"/home/step/artifacts/{name}.crt", f"/home/step/artifacts/{name}.key",
           "--ca", "/home/step/certs/intermediate_ca.crt", "--ca-key", "/home/step/secrets/intermediate_ca_key",
           "--ca-password-file", "/home/step/secrets/password",
           "--no-password", "--insecure", "--force", "--bundle",
           "--kty", str(kty), "--not-after", f"{int(days) * 24}h"]
    if str(kty).upper() == "RSA":
        cmd += ["--size", str(int(size))]
    elif crv:
        cmd += ["--crv", str(crv)]
    if is_ca:
        cmd += ["--template", "/home/step/templates/certs/subca.tpl", "--set", f"pathLen={int(path_len)}"]
    else:
        cmd += ["--template", "/home/step/templates/certs/leaf.tpl"]
        for san in dict.fromkeys([cn, *sans]):
            cmd += ["--san", san]
    run_step(v, cmd)
    return os.path.join(artifacts, f"{name}.crt"), os.path.join(artifacts, f"{name}.key")
