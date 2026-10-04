import os
import shutil
import subprocess
from datetime import datetime, timezone

from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.pki.mint_extra_cert import mint_extra_cert


def _ask(prompt, default=""):
    """Purpose: one prompt with a default.
    Inputs:  prompt — text; default — returned for an empty answer.
    Returns: the answer (str), stripped.
    Fails:   EOFError when stdin is closed.
    Feeds:   run_mint_certs_command."""
    answer = input(f"  {prompt}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def _show(crt):
    """Purpose: print where a minted certificate is and what it says.
    Inputs:  crt — the certificate's path (its key is next to it, .key).
    Returns: None.
    Fails:   never (openssl's errors are not shown).
    Feeds:   run_mint_certs_command."""
    print(f"[+] Certificate minted: {crt} (key: {crt[:-4] if crt.endswith('.crt') else crt}.key)")
    subprocess.run(["openssl", "x509", "-in", crt, "-noout", "-subject", "-dates", "-ext", "basicConstraints",
                    "-ext", "subjectAltName"], stderr=subprocess.DEVNULL)


def run_mint_certs_command(vars_path, archive_dir, args):
    """Purpose: `fabricctl --mint-certs`: offline certificates signed by Step-CA. With --apply every extra_certs entry
             in vars.yaml is minted; otherwise one is asked for (a leaf, or with --intermediate-ca [N] a subordinate
             CA with path length N, default 0), recorded in vars.yaml and minted.
    Inputs:  vars_path — vars.yaml; archive_dir — <fabric>/archive (a copy of vars.yaml before it changes);
             args — the words after --mint-certs: --apply, --intermediate-ca [N], --kty RSA|EC|OKP (default RSA),
             --size BITS (default 4096); prompts on stdin.
    Returns: exit status: 0 (also when cancelled or nothing to mint), 1 when vars.yaml is missing or the Common Name
             is empty.
    Fails:   whatever mint_extra_cert raises (SetupError from step-ca, ValidationError for a bad entry); EOFError at a
             prompt without stdin.
    Feeds:   cli.py (--mint-certs); the same minting as setup (pki/mint_extra_cert).
    Notes:   the entry is built as data (never text pasted into JSON), recorded under vars_lock."""
    if not os.path.exists(vars_path):
        print(f"[✗] fabric not deployed ({vars_path} not found).")
        return 1
    if "--apply" in args:
        entries = load_vars(vars_path).get("extra_certs") or []
        if not entries:
            print("[!] No extra_certs entries in vars.yaml — nothing to mint.")
            return 0
        for entry in entries:
            _show(mint_extra_cert(load_vars(vars_path), entry))
        print("[+] Certificate minting complete.")
        return 0

    is_ca = "--intermediate-ca" in args
    path_len = 0
    if is_ca:
        i = args.index("--intermediate-ca") + 1
        path_len = int(args[i]) if i < len(args) and args[i].isdigit() else 0
    kty = args[args.index("--kty") + 1] if "--kty" in args else "RSA"
    size = args[args.index("--size") + 1] if "--size" in args else "4096"

    print(f"[*] Interactive {'subordinate CA' if is_ca else 'certificate'} minting (signed by Step-CA"
          f"{f', pathLen={path_len}' if is_ca else ''})\n")
    cn = _ask("Common Name (e.g. myservice.internal)")
    if not cn:
        print("[✗] Common Name is required.")
        return 1
    sans = []
    if not is_ca:
        print("  Additional SANs (blank to finish):")
        while True:
            san = input("    SAN: ").strip()
            if not san:
                break
            sans.append(san)
    days = int(_ask("Validity in days", "365"))
    out_dir = _ask("Output directory [caller's home]")
    kty = _ask("Key type", kty)
    size = int(_ask("Key size", str(size)))

    entry = {"cn": cn, "sans": sans, "days": days, "kty": kty, "size": size}
    if is_ca:
        entry.update(is_ca=True, path_len=path_len)
    if out_dir:
        entry["out_dir"] = out_dir
    kind = (f"Subordinate CA (pathLen={path_len})" if is_ca else "Leaf")
    print(f"\n  CN: {cn}\n  Type: {kind}\n  Key: {kty} {size}\n  Days: {days}"
          + "".join(f"\n    SAN {s}" for s in sans) + f"\n  Output: {out_dir or 'caller home'}\n")
    if input("  Add to vars.yaml and mint? [y/N] ").strip().lower() not in ("y", "yes"):
        print("[*] Cancelled.")
        return 0

    with vars_lock():
        os.makedirs(os.path.join(archive_dir, "vars"), exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        shutil.copy(vars_path, os.path.join(archive_dir, "vars", f"{stamp}_mint-certs_{cn}.yaml"))
        data = load_vars(vars_path)
        data["extra_certs"] = list(data.get("extra_certs") or []) + [entry]
        save_vars(data, vars_path)
    print("[+] vars.yaml updated")
    _show(mint_extra_cert(load_vars(vars_path), entry))
    print(f"[+] Certificate for '{cn}' minted.")
    return 0
