import os
import shutil
import subprocess

from fabriclib.common.console import info, ok, warn
from fabriclib.common.one_time_password import one_time_password
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.keycloak.require_password_change import require_password_change
from fabriclib.ldap.ensure_admin_user import ensure_admin_user
from fabriclib.ldap.ensure_posix_identities import ensure_posix_identities
from fabriclib.ldap.people_written_here import people_written_here
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
    """Purpose: write a private file for the operator.
    Inputs:  path — destination; text — content; owner — (uid, gid).
    Returns: None; file 0600 (created under umask 077) owned by owner.
    Fails:   OSError on write, chmod or chown.
    Feeds:   run (initial-password.txt, <user>.crt, p12-password.txt, README.txt)."""
    old = os.umask(0o077)
    try:
        with open(path, "w") as f:
            f.write(text)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
    os.chown(path, *owner)


def run(ctx):
    """Purpose: the first web UI admin, end to end: an LDAP user in the admin group (Keycloak grants it
             fabric-admin), a client certificate (.p12, CN = username) and the fabric root CA, collected with
             instructions in ~/fabric-admin of the account that ran setup.
    Inputs:  ctx — SetupContext: vars install_webui, install_keycloak, install_ldap (default True),
             webui_admin_user, webui_admin_email, webui_admin_group (default admins), webui_client_cert_days
             (default 365), domain, hostname_mgr, hostname_certs, host_ip; secrets (Keycloak admin); the
             published CA under <deploy_base>/nginx/www/certs. Env SUDO_USER via sudo_owner.
    Returns: None. Without web UI, Keycloak or LDAP: nothing. At a federated site the person is not created here
             (people come from the root, M5): only the client certificate and the kit. Otherwise the kit folder (0700)
             holds root-ca.crt/.cer,
             README.txt and, when due, <user>.p12, <user>.crt and p12-password.txt; initial-password.txt only when
             the user was created (then Keycloak forces a password change). Idempotent: an existing user keeps
             their password; the certificate is renewed when due or from another CA.
    Fails:   ValidationError from ensure_admin_user, require_password_change or issue_client_cert (propagates,
             not SetupError); CalledProcessError from openssl; OSError on files. Warns when run as root without sudo.
    Feeds:   setup step `admin`, run by run_setup via STEPS."""
    v = ctx.vars
    if not (v.get("install_webui") and v.get("install_keycloak") and v.get("install_ldap", True)):
        ok("no web UI: nothing to do")
        return
    user = v.get("webui_admin_user")
    login, home, uid, gid = sudo_owner()
    folder = os.path.join(home, "fabric-admin")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chown(folder, uid, gid)

    if people_written_here(os.path.join(ctx.config_dir, "federation.yaml")):
        password = one_time_password(24)
        state = ensure_admin_user(v, user, password, v.get("webui_admin_email") or f"{user}@{v['domain']}")
        if state.startswith("created"):
            require_password_change(v, ctx.secrets, user)
            _write(os.path.join(folder, "initial-password.txt"), password + "\n", (uid, gid))
            ok(f"admin '{user}' created in 389-DS, member of '{v.get('webui_admin_group', 'admins')}'")
        else:
            ok(f"admin '{user}' exists" + (" (added to the admin group)" if "+member" in state else ""))
        posix = ensure_posix_identities(v)
        if posix["added"]:
            ok("POSIX identity: " + ", ".join(posix["added"]))
    else:                                     # a federated site: people (the admin too) come from the root (M5)
        info(f"people are created at the root site: '{user}' signs in here once the root's directory has them "
             f"(in '{v.get('webui_admin_group', 'admins')}'); their client certificate is issued here")

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
