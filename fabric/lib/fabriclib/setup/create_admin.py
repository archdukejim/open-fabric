import os
import secrets
import shutil
import subprocess

from fabriclib.common.console import info, ok, warn
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.keycloak.require_password_change import require_password_change
from fabriclib.ldap.ensure_admin_user import ensure_admin_user
from fabriclib.pki.issue_client_cert import issue_client_cert
from fabriclib.pki.needs_renewal import needs_renewal

README = """fabric web UI — first login
===========================

Everything your computer needs to reach https://{mgr}:

  root-ca.crt / root-ca.cer     fabric root CA (Linux, macOS, iOS, Android / Windows)
  {user}.p12                    your client certificate (password: p12-password.txt)
  initial-password.txt          your first Keycloak password (changed at first login)

1. Copy this folder to your computer, e.g.
     scp -r {login}@{host}:{folder} .
2. Trust the root CA: Windows: double-click root-ca.cer and put it in
   "Trusted Root Certification Authorities"; macOS/Linux: root-ca.crt. Every
   system, format and installer: https://{certs}
3. Import {user}.p12 into your browser (Firefox: Settings > Certificates >
   Your Certificates > Import; Chrome/Edge/Windows: double-click it).
4. Your computer must resolve {mgr} (use fabric as its DNS server,
   {ip}, or add a hosts entry).
5. Open https://{mgr}, choose the "{user} (fabric)" certificate and log in
   as '{user}'. Keycloak asks you for a new password and to set up an
   authenticator app (TOTP) before the dashboard opens.

Delete initial-password.txt and p12-password.txt once you are in.
More admins: sudo fabricctl client-cert <keycloak-user> (the user must be in
the '{group}' group).
"""


def _write(path, text, owner):
    old = os.umask(0o077)
    try:
        with open(path, "w") as f:
            f.write(text)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
    os.chown(path, *owner)


def run(ctx):
    """The first web UI admin, end to end: an LDAP user in the admin group
    (Keycloak grants it fabric-admin), a client certificate (.p12) whose CN
    is that username, and the fabric root CA — collected with instructions
    in ~/fabric-admin of the account that ran setup. Idempotent: an existing
    user keeps their password; the certificate is renewed when due."""
    v = ctx.vars
    if not (v.get("install_webui") and v.get("install_keycloak") and v.get("install_ldap", True)):
        ok("no web UI: nothing to do")
        return
    user = v.get("webui_admin_user")
    login, home, uid, gid = sudo_owner()
    folder = os.path.join(home, "fabric-admin")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chown(folder, uid, gid)

    password = secrets.token_urlsafe(18)
    state = ensure_admin_user(v, user, password, v.get("webui_admin_email") or f"{user}@{v['domain']}")
    if state.startswith("created"):
        require_password_change(v, ctx.secrets, user)
        _write(os.path.join(folder, "initial-password.txt"), password + "\n", (uid, gid))
        ok(f"admin '{user}' created in 389-DS, member of '{v.get('webui_admin_group', 'admins')}'")
    else:
        ok(f"admin '{user}' exists" + (" (added to the admin group)" if "+member" in state else ""))

    crt_pub = os.path.join(folder, f"{user}.crt")
    certs = ctx.path("stepca", "data", "certs")
    ca = (os.path.join(certs, "root_ca.crt"), os.path.join(certs, "intermediate_ca.crt"))
    # A kit left from an earlier install (other CA) is replaced too.
    if needs_renewal(crt_pub, [], ca) or not os.path.exists(os.path.join(folder, f"{user}.p12")):
        p12, p12_password = issue_client_cert(v, user, folder, owner=(uid, gid),
                                              days=int(v.get("webui_client_cert_days", 365)))
        pub = subprocess.run(["openssl", "pkcs12", "-in", p12, "-clcerts", "-nokeys", "-passin", "stdin"],
                             input=p12_password, capture_output=True, text=True, check=True).stdout
        _write(crt_pub, pub[pub.index("-----BEGIN CERTIFICATE"):], (uid, gid))
        os.chmod(crt_pub, 0o644)
        _write(os.path.join(folder, "p12-password.txt"), p12_password + "\n", (uid, gid))
        ok(f"client certificate {p12}")
    else:
        ok(f"client certificate for '{user}' is current")

    www = ctx.path("nginx", "www", "certs")
    for name in ("root-ca.crt", "root-ca.cer"):
        shutil.copy2(os.path.join(www, name), os.path.join(folder, name))
        os.chown(os.path.join(folder, name), uid, gid)
    _write(os.path.join(folder, "README.txt"),
           README.format(mgr=v["hostname_mgr"], certs=v["hostname_certs"], user=user,
                         login=login, host=v["host_ip"], ip=v["host_ip"], folder=folder,
                         group=v.get("webui_admin_group", "admins")), (uid, gid))
    info(f"web UI login kit: {folder} (see README.txt)")
    if login == "root":
        warn("setup was not run with sudo from a user account: the kit is in /root")
