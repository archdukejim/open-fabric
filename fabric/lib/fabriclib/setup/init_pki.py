import json
import os
import shutil
import subprocess

from fabriclib.common.console import info, ok
from fabriclib.setup.errors import SetupError


def _chown_tree(path, uid, gid):
    for root, dirs, files in os.walk(path):
        for name in [root] + [os.path.join(root, n) for n in dirs + files]:
            os.chown(name, uid, gid)


def _configure_ca_json(ca_json, v):
    with open(ca_json) as f:
        cfg = json.load(f)
    if v.get("byoc"):
        cfg["root"] = "/home/step/certs/root_ca.crt"
        cfg["crt"] = "/home/step/certs/intermediate_ca.crt"
        cfg["key"] = "/home/step/secrets/intermediate_ca_key"
    cfg["dnsNames"] = [v["hostname_stepca"], "localhost", "127.0.0.1"]
    auth = cfg["authority"]
    auth.setdefault("claims", {})["maxTLSCertDuration"] = str(v.get("stepca_cert_max_lifetime_hours", "131400h"))
    provisioners = auth.setdefault("provisioners", [])
    if not any(p.get("type") == "ACME" for p in provisioners):
        provisioners.append({"type": "ACME", "name": "acme"})
    for p in provisioners:
        if p.get("type") == "JWK" and v.get("stepca_cert_allow_subordinate_ca"):
            p.setdefault("options", {}).setdefault("x509", {})["allowedExtensions"] = ["2.5.29.19"]
        if p.get("type") == "ACME":
            life = str(v.get("cert_acme_lifetime_hours", "2160h"))
            p.setdefault("claims", {}).update({"defaultTLSCertDuration": life, "maxTLSCertDuration": life})
            p.setdefault("options", {})["x509"] = {"templateFile": "/home/step/templates/certs/leaf.tpl"}
    with open(ca_json, "w") as f:
        json.dump(cfg, f, indent="\t")


def _publish_ca_certs(ctx, certs_dir):
    """CA certs on the landing page (PEM + DER for Windows) and in the host trust store."""
    v = ctx.vars
    www = ctx.path("nginx", "www", "certificates")
    os.makedirs(www, exist_ok=True)
    nginx_uid, nginx_gid = ctx.uid("nginx")
    for src, name, der_name in (("root_ca.crt", v["root_cert_name"], f"{v['root_cert_name']}_win"),
                                ("intermediate_ca.crt", f"{v['domain_file']}_ca", f"{v['domain_file']}_win_ca")):
        pem = os.path.join(www, f"{name}.crt")
        shutil.copy2(os.path.join(certs_dir, src), pem)
        der = os.path.join(www, f"{der_name}.cer")
        subprocess.run(["openssl", "x509", "-in", pem, "-out", der, "-outform", "der"], check=True)
        for path in (pem, der):
            os.chown(path, nginx_uid, nginx_gid)
            os.chmod(path, 0o644)
        shutil.copy2(pem, f"/usr/local/share/ca-certificates/{name}.crt")
    subprocess.run(["update-ca-certificates", "--fresh"], check=True, capture_output=True)


def _public_certs_readable(certs_dir):
    """root_ca.crt / intermediate_ca.crt are public: the web UI (mounted
    read-only at /certs) verifies client certificates against them. step ca
    init creates the directory 0700; keys live in secrets/, never here."""
    os.chmod(certs_dir, 0o755)
    for name in os.listdir(certs_dir):
        if name.endswith(".crt"):
            os.chmod(os.path.join(certs_dir, name), 0o644)


def run(ctx):
    """Initialise Step-CA once (its own chain, or a bring-your-own root +
    intermediate when byoc), configure ca.json, publish the CA certs and
    trust them on the host. Skipped when ca.json already exists."""
    v = ctx.vars
    data = ctx.path("stepca", "data")
    ca_json = os.path.join(data, "config", "ca.json")
    uid, gid = ctx.uid("step")
    if os.path.exists(ca_json):
        _public_certs_readable(os.path.join(data, "certs"))
        ok("Step-CA already initialised")
        return

    if v.get("byoc"):
        ica_key = v.get("ica_key_path") or os.path.splitext(v.get("ica_crt_path", ""))[0] + ".key"
        missing = [p for p in (v.get("ca_crt_path"), v.get("ica_crt_path"), ica_key) if not p or not os.path.exists(p)]
        if missing:
            raise SetupError(f"byoc: missing root/intermediate files: {', '.join(map(str, missing))}")

    os.makedirs(os.path.join(data, "secrets"), mode=0o750, exist_ok=True)
    pw = os.path.join(data, "secrets", "password")
    with open(pw, "w") as f:
        f.write(ctx.secrets["ca_password"])
    os.chmod(pw, 0o600)
    _chown_tree(data, uid, gid)

    info("initialising Step-CA")
    res = subprocess.run(["docker", "run", "--rm", "-v", f"{data}:/home/step", "-e", "STEPPATH=/home/step",
                          "-u", f"{uid}:{gid}", "--entrypoint", "/usr/local/bin/step", v["image_stepca"],
                          "ca", "init", f"--name={v['ca_name']}",
                          f"--dns={v['hostname_stepca']},localhost,127.0.0.1",
                          f"--address=:{v.get('stepca_port', 9000)}", "--provisioner=admin",
                          "--password-file=/home/step/secrets/password",
                          "--provisioner-password-file=/home/step/secrets/password"],
                         capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(ca_json):
        raise SetupError(f"step ca init failed: {(res.stderr or res.stdout)[-600:]}")

    certs = os.path.join(data, "certs")
    if v.get("byoc"):
        shutil.copy2(v["ca_crt_path"], os.path.join(certs, "root_ca.crt"))
        with open(os.path.join(certs, "intermediate_ca.crt"), "w") as out:
            for p in (v["ica_crt_path"], v["ca_crt_path"]):
                out.write(open(p).read())
        shutil.copy2(ica_key, os.path.join(data, "secrets", "intermediate_ca_key"))
        os.chmod(os.path.join(data, "secrets", "intermediate_ca_key"), 0o600)

    _configure_ca_json(ca_json, v)
    _chown_tree(data, uid, gid)
    _public_certs_readable(certs)
    subprocess.run(["openssl", "verify", "-CAfile", os.path.join(certs, "root_ca.crt"),
                    os.path.join(certs, "intermediate_ca.crt")], check=True, capture_output=True)
    _publish_ca_certs(ctx, certs)
    ok(f"Step-CA initialised ({'bring-your-own root' if v.get('byoc') else 'own root'}), CA certs published and trusted")
