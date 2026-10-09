import glob
import os
import pwd
import shutil
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.secrets.save_secrets import save_secrets

UNITS = {"adguard": "adguardhome", "adguard-auth": "oauth2-proxy-adguard"}       # unit -> its container
ACCOUNTS = {"fabric-dnsfilter": 611, "fabric-auth": 612}                         # name -> uid (and gid), 0.6's
SECRETS = ("adguard_admin_password", "adguard_oidc_secret", "adguard_cookie_secret")


def retire_adguard(v, secrets, secrets_file, config_dir):
    """Purpose: upgrade step of 0.7 (decision 2.1.12.3, manual 2.3.12.1.9): AdGuard Home leaves a host that ran it —
             its units and containers (so the BIND resolver can take port 53), its folders, nginx's sign-in snippet,
             its local image, its secrets and its two service accounts. Its settings were moved by setup's
             move_dns_filter first; its folders go only once that record exists.
    Inputs:  v — rendered vars (deploy_base_dir, dns_filter); secrets — fabric's secrets (None: not loaded);
             secrets_file — where they live (the file, or OpenBao through it); config_dir — fabric's config folder
             (the dns-filter-import-*.json record).
    Returns: list of what was retired (str); [] when nothing of AdGuard was left. Idempotent.
    Fails:   OSError removing a file or folder. systemctl, docker and userdel failures are ignored (a later run
             retires what is left); a secrets store that cannot be written (OpenBao locked) leaves the secrets,
             reported in the list.
    Feeds:   setup/start_services (before the units start: the resolver needs port 53)."""
    if str(v.get("dns_filter") or "").lower() == "adguard":
        return []                                       # not moved (cannot happen after collect_vars): leave it
    done = []
    for unit, container in UNITS.items():
        path = f"/etc/systemd/system/{unit}.service"
        if os.path.exists(path):
            subprocess.run(["systemctl", "disable", "--now", unit], capture_output=True)
            os.remove(path)
            done.append(f"unit {unit}")
        if subprocess.run(["docker", "rm", "-f", container], capture_output=True).returncode == 0:
            done.append(f"container {container}")
    if any(d.startswith("unit ") for d in done):
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    base = v.get("deploy_base_dir") or "/opt"
    recorded = glob.glob(os.path.join(config_dir, "dns-filter-import-*.json"))
    for folder in ("adguard", "adguard-auth"):
        path = os.path.join(base, folder)
        if not os.path.isdir(path):
            continue
        if folder == "adguard" and os.path.exists(os.path.join(path, "conf", "AdGuardHome.yaml")) and not recorded:
            done.append(f"{path} kept: its settings were not recorded yet (run sudo fabricctl setup)")
            continue
        shutil.rmtree(path)
        done.append(f"folder {path}")
    snippet = os.path.join(base, "nginx", "config", "conf.d", "adguard-auth.inc")
    if os.path.exists(snippet):
        os.remove(snippet)
        done.append(f"file {snippet}")
    if subprocess.run(["docker", "rmi", "fabric/adguard:local"], capture_output=True).returncode == 0:
        done.append("image fabric/adguard:local")
    if secrets and any(k in secrets for k in SECRETS):
        try:
            save_secrets({k: None for k in SECRETS}, secrets_file)
            done.append("secrets " + ", ".join(k for k in SECRETS if k in secrets))
        except ValidationError as e:
            done.append(f"secrets kept for now ({e}): the next setup run removes them")
    for name, uid in ACCOUNTS.items():
        try:
            if pwd.getpwnam(name).pw_uid != uid:
                continue                                # not fabric's: never touched
        except KeyError:
            continue
        if subprocess.run(["userdel", name], capture_output=True).returncode == 0:
            subprocess.run(["groupdel", name], capture_output=True)
            done.append(f"account {name}")
    return done
