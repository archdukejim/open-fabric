import os
import re
import shutil

from fabriclib.common.errors import ValidationError
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.pki.mint_offline_cert import mint_offline_cert


def extra_cert_paths(entry):
    """Purpose: Where one extra_certs entry's certificate and key go, and who owns them.
    Inputs:  entry — dict with "cn" and optional "out_dir". Reads SUDO_USER (sudo_owner).
    Returns: (crt_path, key_path, (uid, gid)): <out_dir, else the sudo user's home>/<cn with ".", "/" and
             " " as "-">.crt / .key; the owner is always the sudo user (root without sudo).
    Fails:   KeyError if entry has no "cn".
    Feeds:   mint_extra_cert; setup/mint_extra_certs.py mint_extra_certs (renewal check).
    """
    _, home, uid, gid = sudo_owner()
    out = entry.get("out_dir") or home
    safe = re.sub(r"[./ ]", "-", entry["cn"])
    return os.path.join(out, f"{safe}.crt"), os.path.join(out, f"{safe}.key"), (uid, gid)


def mint_extra_cert(v, entry):
    """Purpose: Mint one extra_certs entry with the Step-CA intermediate and write its certificate and
             key where the entry says.
    Inputs:  v — fabric vars; entry — {cn (required), sans, days (365), kty ("RSA"), size (4096), is_ca,
             path_len (0), out_dir (default: the sudo user's home)}; no "crv" is passed on, so an EC entry
             gets step's default curve.
    Returns: the crt path (chain, 0644); the key lies next to it (0600); both owned by the sudo user and
             replacing any existing files.
    Fails:   ValidationError "output directory does not exist: ..."; mint_offline_cert's ValidationError
             (invalid name, "step-ca refused: ..."); KeyError without "cn"; OSError from move / chown.
    Feeds:   setup/mint_extra_certs.py mint_extra_certs; fabriclib/cli.py `extra-cert` (fabricctl
             --mint-certs from pki/run_mint_certs_command / interactive.py).
    """
    crt_out, key_out, owner = extra_cert_paths(entry)
    if not os.path.isdir(os.path.dirname(crt_out)):
        raise ValidationError(f"output directory does not exist: {os.path.dirname(crt_out)}")
    crt, key = mint_offline_cert(v, entry["cn"], entry.get("sans") or [], days=entry.get("days", 365),
                                 kty=entry.get("kty", "RSA"), size=entry.get("size", 4096),
                                 is_ca=bool(entry.get("is_ca")), path_len=entry.get("path_len", 0))
    shutil.move(key, key_out)
    shutil.move(crt, crt_out)
    for path, mode in ((key_out, 0o600), (crt_out, 0o644)):
        os.chown(path, *owner)
        os.chmod(path, mode)
    return crt_out
