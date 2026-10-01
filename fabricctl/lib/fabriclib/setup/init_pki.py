import json
import os
import shutil
import subprocess

from fabriclib.common.console import info, ok
from fabriclib.pki.publish_ca_certs import publish_ca_certs
from fabriclib.setup.errors import SetupError


def _chown_tree(path, uid, gid):
    """Purpose: give a whole directory tree to one owner.
    Inputs:  path — root of the tree; uid, gid — ints.
    Returns: None; path and everything below it chowned (symlinks followed).
    Fails:   OSError from os.chown.
    Feeds:   run (Step-CA's data folder to the step user)."""
    for root, dirs, files in os.walk(path):
        for name in [root] + [os.path.join(root, n) for n in dirs + files]:
            os.chown(name, uid, gid)


def _configure_ca_json(ca_json, v):
    """Purpose: converge Step-CA's ca.json after `step ca init`: bring-your-own chain paths, DNS names,
             certificate lifetimes, an ACME provisioner with fabric's leaf template.
    Inputs:  ca_json — path to ca.json; v — vars: byoc, hostname_stepca, stepca_cert_max_lifetime_hours
             (default 131400h), stepca_cert_allow_subordinate_ca, cert_acme_lifetime_hours (default 2160h).
    Returns: None; ca.json rewritten (tab-indented). With stepca_cert_allow_subordinate_ca the JWK provisioner
             may issue the basicConstraints extension (2.5.29.19).
    Fails:   OSError/json.JSONDecodeError reading ca.json; KeyError without hostname_stepca or
             "authority" in ca.json.
    Feeds:   run."""
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


def _single_intermediate(path):
    """Purpose: keep only the intermediate certificate in intermediate_ca.crt, the layout `step ca init` makes:
             the step CLI's offline signing (mint_offline_cert, sign_csr) takes exactly one certificate as --ca.
             Earlier bring-your-own installs appended the root there.
    Inputs:  path — Step-CA's certs/intermediate_ca.crt.
    Returns: True if the file held more than one certificate and was rewritten with the first one.
    Fails:   OSError reading or writing the file.
    Feeds:   run (first initialisation with byoc, and every later run, so existing installs converge)."""
    with open(path) as f:
        text = f.read()
    end = "-----END CERTIFICATE-----"
    if text.count(end) <= 1:
        return False
    with open(path, "w") as f:
        f.write(text[:text.index(end) + len(end)] + "\n")
    return True


def _publish_ca_certs(ctx, certs_dir):
    """Purpose: publish every CA format on certs.<domain> and trust the CA on this host; done on every
             setup, since a reinstall keeps the CA but not /opt/nginx or the host trust entries.
    Inputs:  ctx — SetupContext: vars.domain_file, service user nginx (uid/gid); certs_dir — Step-CA certs folder.
    Returns: True if anything changed (from publish_ca_certs).
    Fails:   CalledProcessError from openssl/update-ca-certificates and OSError inside publish_ca_certs;
             KeyError without domain_file.
    Feeds:   run."""
    return publish_ca_certs(certs_dir, ctx.path("nginx", "www", "certs"), *ctx.uid("nginx"),
                            trust_prefix=f"fabric-{ctx.vars['domain_file']}")


def _public_certs_readable(certs_dir):
    """Purpose: make the public CA certificates world-readable: the web UI (mounted read-only at /certs)
             verifies client certificates against root_ca.crt/intermediate_ca.crt. `step ca init` creates the
             folder 0700; keys live in secrets/, never here.
    Inputs:  certs_dir — Step-CA certs folder.
    Returns: None; the folder 0755, every *.crt in it 0644.
    Fails:   OSError if the folder is missing or chmod fails.
    Feeds:   run."""
    os.chmod(certs_dir, 0o755)
    for name in os.listdir(certs_dir):
        if name.endswith(".crt"):
            os.chmod(os.path.join(certs_dir, name), 0o644)


def run(ctx):
    """Purpose: initialise Step-CA once (its own root, or a bring-your-own root + intermediate when byoc),
             configure ca.json, publish the CA certificates and trust them on the host.
    Inputs:  ctx — SetupContext: vars byoc, ca_crt_path, ica_crt_path, ica_key_path (default: the .crt path
             with .key), image_stepca, ca_name, hostname_stepca, stepca_port (default 9000) and the ca.json
             settings; secrets.ca_password; service user step.
    Returns: None. First run: <deploy_base>/stepca/data with the CA (password file 0600, owned by step) and
             ca.json configured, chain verified, published and trusted; intermediate_ca.crt holds the
             intermediate alone (also converged on later runs, restarting stepca). With byoc the brought-in intermediate
             key may be encrypted with ca_password (a federation site's is) or not; the root key `step ca
             init` generated is removed, since it does not belong to the brought-in root. With an existing ca.json only the
             permissions, publishing and trust are (re)done.
    Fails:   SetupError when byoc files are missing or `step ca init` fails; CalledProcessError when
             `openssl verify` rejects the intermediate or from publishing; ValidationError from ctx.secrets
             when the secrets are in a locked OpenBao (not converted to SetupError); KeyError for missing vars.
    Feeds:   setup step `pki`, run by run_setup via STEPS."""
    v = ctx.vars
    data = ctx.path("stepca", "data")
    ca_json = os.path.join(data, "config", "ca.json")
    uid, gid = ctx.uid("step")
    if os.path.exists(ca_json):
        if _single_intermediate(os.path.join(data, "certs", "intermediate_ca.crt")):
            ctx.restart_services.add("stepca")
            ok("intermediate_ca.crt: the intermediate alone (the root it carried is in root_ca.crt)")
        _public_certs_readable(os.path.join(data, "certs"))
        published = _publish_ca_certs(ctx, os.path.join(data, "certs"))
        ok("Step-CA already initialised" + ("; CA certs re-published and trusted" if published else ""))
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
        shutil.copy2(v["ica_crt_path"], os.path.join(certs, "intermediate_ca.crt"))
        _single_intermediate(os.path.join(certs, "intermediate_ca.crt"))
        shutil.copy2(ica_key, os.path.join(data, "secrets", "intermediate_ca_key"))
        os.chmod(os.path.join(data, "secrets", "intermediate_ca_key"), 0o600)
        # `step ca init` made a root of its own: its key signs nothing that chains to the brought-in root
        os.remove(os.path.join(data, "secrets", "root_ca_key"))

    _configure_ca_json(ca_json, v)
    _chown_tree(data, uid, gid)
    _public_certs_readable(certs)
    subprocess.run(["openssl", "verify", "-CAfile", os.path.join(certs, "root_ca.crt"),
                    os.path.join(certs, "intermediate_ca.crt")], check=True, capture_output=True)
    _publish_ca_certs(ctx, certs)
    ok(f"Step-CA initialised ({'bring-your-own root' if v.get('byoc') else 'own root'}), CA certs published and trusted")
