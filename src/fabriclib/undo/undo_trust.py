import os
import subprocess

from fabriclib.pki.publish_ca_certs import TRUST_DIR


def undo_trust(v):
    """Purpose: undo the `trust` host change (manual 2.7.1.5): fabric's root and intermediate CA out of
             this host's trust store.
    Inputs:  v — vars: domain_file (the trust files' prefix, pki/publish_ca_certs).
    Returns: list of str, what was done (empty when nothing was there).
    Fails:   OSError removing a file; a failing update-ca-certificates is ignored.
    Feeds:   undo/undo_group (`fabricctl setup --undo trust`), setup/uninstall."""
    if not v.get("domain_file"):
        return []
    done = []
    for name in ("root-ca", "intermediate-ca"):
        path = os.path.join(TRUST_DIR, f"fabric-{v['domain_file']}-{name}.crt")
        if os.path.exists(path):
            os.remove(path)
            done.append(f"{path} removed")
    if done:
        subprocess.run(["update-ca-certificates", "--fresh"], capture_output=True)
        done.append("update-ca-certificates: this host no longer trusts fabric's CA")
    return done
