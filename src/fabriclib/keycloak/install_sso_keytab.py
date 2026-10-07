import os
import shutil

from fabriclib.common.write_file_if_changed import write_file_if_changed


def install_sso_keytab(v):
    """Purpose: give Keycloak the site's Kerberos sign-in keytab (manual 5.8.2.6.2): the DC exports it to its data
             folder (src/containers/samba/ensure_sso_account); this copies it to Keycloak's kerberos folder (0400,
             Keycloak's user) with a krb5.conf that maps fabric's domain and the AD domain to the AD realm. Without a
             keytab at the DC (Kerberos sign-in off, a read-only DC), Keycloak's copy is removed.
    Inputs:  v — rendered vars: deploy_base_dir, ad_domain, domain, host_ip, service_users (keycloak).
    Returns: bool, whether Keycloak's files changed (Keycloak restarts to read them).
    Fails:   OSError reading or writing; KeyError for a missing var.
    Feeds:   setup/start_services, deploy/restart_changed (after converge_domain)."""
    base = v["deploy_base_dir"]
    src = os.path.join(base, "samba", "data", "sso.keytab")
    folder = os.path.join(base, "keycloak", "kerberos")
    dst = os.path.join(folder, "sso.keytab")
    if not os.path.exists(src):
        if not os.path.exists(dst):
            return False
        os.remove(dst)
        return True
    uid, gid = (int(v["service_users"]["keycloak"][k]) for k in ("uid", "gid"))
    os.makedirs(folder, mode=0o750, exist_ok=True)
    os.chown(folder, 0, gid)
    realm = v["ad_domain"].upper()
    krb5 = (f"# fabric (manual 5.8.2.6.2): Keycloak accepts tickets of the AD realm for fabric's names\n"
            f"[libdefaults]\n  default_realm = {realm}\n  dns_lookup_kdc = false\n  rdns = false\n"
            f"[realms]\n  {realm} = {{\n    kdc = {v['host_ip']}\n  }}\n"
            f"[domain_realm]\n  .{v['domain']} = {realm}\n  .{v['ad_domain']} = {realm}\n")
    changed = write_file_if_changed(os.path.join(folder, "krb5.conf"), krb5, 0o444, 0, gid)
    with open(src, "rb") as f:
        data = f.read()
    old = open(dst, "rb").read() if os.path.exists(dst) else None
    if data != old:
        tmp = dst + ".new"
        with open(tmp, "wb") as f:
            f.write(data)
        os.chown(tmp, uid, gid)
        os.chmod(tmp, 0o400)
        shutil.move(tmp, dst)
        changed = True
    return changed
