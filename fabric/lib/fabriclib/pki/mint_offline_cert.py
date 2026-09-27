import os
import re
import subprocess

from fabriclib.common.errors import ValidationError

CN_RE = re.compile(r"^[A-Za-z0-9*][A-Za-z0-9._@*-]{0,252}$")


def mint_offline_cert(v, cn, sans=(), days=365, kty="RSA", size=4096, is_ca=False, path_len=0):
    """Sign a certificate directly with the Step-CA intermediate key (works
    whether or not step-ca is running). Leaf certs use the leaf template;
    is_ca issues a subordinate CA (subca template, pathLen). Returns
    (crt_path, key_path) in stepca/data/artifacts; the crt carries the chain
    (--bundle). The caller moves or deletes both files."""
    if not CN_RE.match(cn):
        raise ValidationError(f"invalid certificate name: {cn!r}")
    base = v["deploy_base_dir"]
    data = os.path.join(base, "stepca", "data")
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    artifacts = os.path.join(data, "artifacts")
    os.makedirs(artifacts, mode=0o750, exist_ok=True)
    os.chown(artifacts, uid, gid)
    name = re.sub(r"[./ @*]", "-", cn)
    cmd = ["docker", "run", "--rm", "-v", f"{data}:/home/step", "--user", f"{uid}:{gid}",
           "--entrypoint", "/usr/local/bin/step", v["image_stepca"],
           "certificate", "create", cn, f"/home/step/artifacts/{name}.crt", f"/home/step/artifacts/{name}.key",
           "--ca", "/home/step/certs/intermediate_ca.crt", "--ca-key", "/home/step/secrets/intermediate_ca_key",
           "--ca-password-file", "/home/step/secrets/password",
           "--no-password", "--insecure", "--force", "--bundle",
           "--kty", str(kty), "--not-after", f"{int(days) * 24}h"]
    if str(kty).upper() == "RSA":
        cmd += ["--size", str(int(size))]
    if is_ca:
        cmd += ["--template", "/home/step/templates/certs/subca.tpl", "--set", f"pathLen={int(path_len)}"]
    else:
        cmd += ["--template", "/home/step/templates/certs/leaf.tpl"]
        for san in dict.fromkeys([cn, *sans]):
            cmd += ["--san", san]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise ValidationError(f"minting {cn} failed: {(res.stderr or res.stdout)[-500:]}")
    return os.path.join(artifacts, f"{name}.crt"), os.path.join(artifacts, f"{name}.key")
