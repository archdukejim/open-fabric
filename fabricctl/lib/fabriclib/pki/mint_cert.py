import os
import subprocess

from fabriclib.setup.errors import SetupError


def mint_cert(ctx, cn, sans, name):
    """Issue a TLS server/client certificate from the running step-ca
    (JWK provisioner `admin`). Returns (fullchain_path, key_path) in
    <base>/stepca/data/artifacts; the chain includes the intermediate."""
    v = ctx.vars
    uid, gid = ctx.uid("step")
    artifacts = ctx.path("stepca", "data", "artifacts")
    os.makedirs(artifacts, mode=0o750, exist_ok=True)
    os.chown(artifacts, uid, gid)
    hours = int(v.get("cert_service_days", 5475)) * 24
    cmd = ["docker", "exec", "-u", f"{uid}:{gid}", "step-ca", "step", "ca", "certificate", cn,
           f"/home/step/artifacts/{name}.crt", f"/home/step/artifacts/{name}.key",
           "--ca-url", f"https://127.0.0.1:{v.get('stepca_port', 9000)}",
           "--root", "/home/step/certs/root_ca.crt", "--provisioner", "admin",
           "--provisioner-password-file", "/home/step/secrets/password",
           "--force", "--kty", "RSA", "--size", "4096", "--not-after", f"{hours}h"]
    for san in dict.fromkeys([cn, *sans]):
        cmd += ["--san", san]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise SetupError(f"minting {cn} failed: {(res.stderr or res.stdout)[-500:]}")

    crt = os.path.join(artifacts, f"{name}.crt")
    key = os.path.join(artifacts, f"{name}.key")
    with open(crt) as f:
        body = f.read()
    if body.count("BEGIN CERTIFICATE") < 2:
        with open(ctx.path("stepca", "data", "certs", "intermediate_ca.crt")) as f:
            body += f.read()
        with open(crt, "w") as f:
            f.write(body)
    return crt, key
