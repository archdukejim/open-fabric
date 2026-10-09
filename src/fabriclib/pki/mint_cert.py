import os
import subprocess

from fabriclib.setup.errors import SetupError


def mint_cert(ctx, cn, sans, name):
    """Purpose: Issue a service TLS certificate from the running step-ca through its JWK provisioner
             `admin` (setup's service certificates).
    Inputs:  ctx — SetupContext: vars (stepca_port default 9000, cert_service_days default 47, manual 2.1.5.4),
             uid("step"), path(); cn — str; sans — list of names (cn is added first, duplicates dropped);
             name — base name of the artifact files.
    Returns: (crt_path, key_path) in <base>/stepca/data/artifacts; RSA 4096; the crt holds the leaf and
             the intermediate (appended from intermediate_ca.crt when step did not bundle it).
    Fails:   SetupError "minting <cn> failed: ..." if step ca certificate fails (e.g. the step-ca container
             is not running); OSError reading or writing the files.
    Feeds:   setup/mint_service_certs.py run.
    Notes:   runs `docker exec step-ca step ca certificate` as the step user; the provisioner password is a
             file path inside the container, never a value on argv.
    """
    v = ctx.vars
    uid, gid = ctx.uid("step")
    artifacts = ctx.path("stepca", "data", "artifacts")
    os.makedirs(artifacts, mode=0o750, exist_ok=True)
    os.chown(artifacts, uid, gid)
    hours = int(v.get("cert_service_days", 47)) * 24
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
