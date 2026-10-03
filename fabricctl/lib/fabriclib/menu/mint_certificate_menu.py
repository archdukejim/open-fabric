import json
import os

from fabriclib.common.console import BLUE, BOLD, GREEN, NC, RED, YELLOW
from fabriclib.common.paths import VARS_FILE
from fabriclib.menu.save_menu_change import save_menu_change
from fabriclib.pki.mint_extra_cert import mint_extra_cert


def mint_certificate_menu(data):
    """Purpose: menu to describe one extra certificate, record it in extra_certs and mint it.
    Inputs:  data — the vars working copy (cert_* values only shown). Asks for CN, SANs, days, key type and size,
             CA (path length 0) and output folder.
    Returns: None when "b" is picked. On "m" the entry is appended to extra_certs, saved, audited and minted
             (pki/mint_extra_cert, the same code as setup); the certificate's path or the error is shown.
    Fails:   an empty CN is refused; a minting failure is shown, not raised (the entry stays recorded); OSError
             saving; EOFError from input().
    Feeds:   run_vars_menu (menu 2)."""
    cert = {"cn": "", "sans": [], "days": 365, "kty": "RSA", "size": 4096, "is_ca": False, "out_dir": ""}
    while True:
        os.system("clear")
        print(f"{BOLD}--- Mint Certificates ---{NC}\n")
        for i, (label, key) in enumerate((("Common Name", "cn"), ("SAN (URL)", "sans"), ("Validity Days", "days"),
                                          ("Key Type", "kty"), ("Key Size", "size"), ("Is CA", "is_ca"),
                                          ("Output Directory", "out_dir")), 1):
            shown = cert[key] if key != "out_dir" else (cert[key] or "(Caller Home)")
            print(f"  {i}) {label + ':':<19} {GREEN}{shown}{NC}")
        print(f"\n{BOLD}System PKI Defaults (will be applied to minted cert):{NC}")
        print(f"  Country: {data.get('cert_country', 'US')} | Province: {data.get('cert_province', 'My Province')} | "
              f"City: {data.get('cert_city', 'My City')}")
        print(f"  Org: {data.get('cert_org', 'My Org')} | OU: {data.get('cert_ou', 'My OU')}")
        print(f"\n  {BOLD}m{NC}) Mint Certificate")
        print(f"  {BOLD}b{NC}) Back to Main Menu")
        choice = input("\nSelect option to edit (1-7), 'm' to mint, or 'b' to go back: ").strip().lower()
        if choice == "b":
            return
        if choice == "1":
            cert["cn"] = input("Common Name: ").strip() or cert["cn"]
        elif choice == "2":
            cert["sans"] = [s.strip() for s in input("SAN (URLs) separated by commas: ").split(",") if s.strip()]
        elif choice in ("3", "5"):
            key = "days" if choice == "3" else "size"
            val = input(f"{'Validity Days' if key == 'days' else 'Key Size'} [{cert[key]}]: ").strip()
            if val.isdigit():
                cert[key] = int(val)
        elif choice == "4":
            cert["kty"] = input(f"Key Type [{cert['kty']}]: ").strip() or cert["kty"]
        elif choice == "6":
            val = input(f"Is CA? (true/false) [{str(cert['is_ca']).lower()}]: ").strip().lower()
            if val in ("true", "yes", "y", "false", "no", "n"):
                cert["is_ca"] = val in ("true", "yes", "y")
        elif choice == "7":
            cert["out_dir"] = input(f"Output Directory [{cert['out_dir']}]: ").strip() or cert["out_dir"]
        elif choice == "m":
            if not cert["cn"]:
                print(f"{RED}Common Name is required!{NC}")
                input("Press Enter to continue...")
                continue
            print(f"\n{BLUE}Preparing to mint certificate...{NC}")
            entry = {k: cert[k] for k in ("cn", "sans", "days", "kty", "size")}
            if cert["is_ca"]:
                entry.update(is_ca=True, path_len=0)
            if cert["out_dir"]:
                entry["out_dir"] = cert["out_dir"]
            data.setdefault("extra_certs", []).append(entry)
            save_menu_change(VARS_FILE, data, "extra_certs", "None", json.dumps(entry), "ADDED")
            print(f"{YELLOW}Saved configuration. Minting certificate...{NC}")
            try:
                print(f"{GREEN}Certificate minted: {mint_extra_cert(data, entry)}{NC}")
            except Exception as e:          # step-ca's refusal or a bad entry: show it, keep the menu
                print(f"{RED}Minting failed: {e}{NC}")
            input("Press Enter to continue...")
