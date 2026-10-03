import json
import os
import shutil
import subprocess

from fabriclib.common.errors import ValidationError


def replace_site_ca(v, staged):
    """Purpose: switch this site's running Step-CA to a new intermediate (a site re-parented under another
             site or the root, manual 1.8.5.1): the new CA certificate, its parent CAs and key replace
             the old ones; the root stays.
    Inputs:  v — fabric vars: deploy_base_dir, service_users.step; staged — stage_site_ca's result
             (ca_crt_path, ica_crt_path, ica_key_path, ica_parents_path).
    Returns: None. stepca/data: certs/intermediate_ca.crt (the new CA alone), certs/ca_parents.crt,
             certs/intermediate_chain.crt (the two together, what ca.json's crt names), secrets/intermediate_ca_key
             (0600), all owned by the step user; the old ones kept as *.old-<n>. The caller restarts stepca and
             re-issues the certificates that came from the old intermediate.
    Fails:   ValidationError "the new CA is for another root" when the staged root is not this site's root;
             OSError; json errors reading ca.json.
    Feeds:   federation/reparent_site.py."""
    data = os.path.join(v["deploy_base_dir"], "stepca", "data")
    certs, secrets_dir = os.path.join(data, "certs"), os.path.join(data, "secrets")
    with open(staged["ca_crt_path"]) as a, open(os.path.join(certs, "root_ca.crt")) as b:
        if a.read().strip() != b.read().strip():
            raise ValidationError("the new CA is for another root")
    n = 1
    while os.path.exists(os.path.join(certs, f"intermediate_ca.crt.old-{n}")):
        n += 1
    for folder, name in ((certs, "intermediate_ca.crt"), (certs, "ca_parents.crt"), (certs, "intermediate_chain.crt"),
                         (secrets_dir, "intermediate_ca_key")):
        if os.path.exists(os.path.join(folder, name)):
            shutil.copy2(os.path.join(folder, name), os.path.join(folder, f"{name}.old-{n}"))
    with open(staged["ica_crt_path"]) as f:
        cert = f.read().strip() + "\n"
    with open(staged["ica_parents_path"]) as f:
        parents = f.read().strip()
    parents = parents + "\n" if parents else ""
    for name, text in (("intermediate_ca.crt", cert), ("ca_parents.crt", parents), ("intermediate_chain.crt", cert + parents)):
        with open(os.path.join(certs, name), "w") as f:
            f.write(text)
        os.chmod(os.path.join(certs, name), 0o644)
    shutil.copy2(staged["ica_key_path"], os.path.join(secrets_dir, "intermediate_ca_key"))
    os.chmod(os.path.join(secrets_dir, "intermediate_ca_key"), 0o600)
    ca_json = os.path.join(data, "config", "ca.json")
    with open(ca_json) as f:
        cfg = json.load(f)
    cfg["crt"] = "/home/step/certs/intermediate_chain.crt"
    with open(ca_json, "w") as f:
        json.dump(cfg, f, indent="\t")
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    subprocess.run(["chown", "-R", f"{uid}:{gid}", data], check=True)
