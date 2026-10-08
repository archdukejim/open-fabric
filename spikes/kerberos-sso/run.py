"""Spike K1 (manual 2.3.6.2.7): Kerberos sign-in (SPNEGO) to Keycloak with a keytab from fabric's Samba DC.

Runs against the containers the keycloak suite leaves when kept (a real DC and a real Keycloak, configured by fabric):
    sudo env KEYCLOAK_TEST_KEEP=1 python3 tests/keycloak/run.py
    sudo python3 spikes/kerberos-sso/run.py
Questions: does a keytab exported by samba-tool for a service account with HTTP SPNs let Keycloak accept a domain
person's ticket; does it work for the name a CNAME points to as well as sso.<domain> (two SPNs, serverPrincipal "*");
which krb5.conf Keycloak needs; whether the AD vendor's principal attribute matches Samba's userPrincipalName.
Throwaway: never merged into src/.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path[0:0] = [os.path.join(REPO, "src"), REPO]
from fabriclib.keycloak.admin_client import Admin  # noqa: E402
from webui.tlsclient import TLSClient  # noqa: E402

DC, KC, NET, DC_IP, KC_IP = "kc-dc", "kc-keycloak", "kctest", "10.254.9.10", "10.254.9.60"
AD_REALM, KC_REALM, HOST, CANON = "AD.J-J.FAMILY", "lan.j-j.family", "sso.lan.j-j.family", "pi-core.lan.j-j.family"
SMB = ["-s", "/data/etc/smb.conf"]
W = tempfile.mkdtemp(prefix="k1-")
ROOT_CA = "/tmp/fabric-tests/keycloak/kc/root_ca.crt"


def sh(cmd, ok=True, **kw):
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if ok and res.returncode:
        raise RuntimeError(f"{' '.join(cmd[:6])}: {(res.stdout + res.stderr).strip()[-600:]}")
    return res


def dc(*args, ok=True):
    return sh(["docker", "exec", DC, *args], ok=ok)


# 1. the service account, its SPNs, its keytab (no password ever leaves the DC)
dc("samba-tool", "user", "create", "fabric-sso-lan", "--random-password", *SMB, ok=False)
dc("samba-tool", "user", "setexpiry", "fabric-sso-lan", "--noexpiry", *SMB)
for spn in (f"HTTP/{HOST}", f"HTTP/{CANON}"):
    dc("samba-tool", "spn", "add", spn, "fabric-sso-lan", *SMB, ok=False)
print(dc("samba-tool", "spn", "list", "fabric-sso-lan", *SMB).stdout.strip())
# AES only (24 = AES128 | AES256): a service account without the attribute gets RC4 tickets, which Java refuses
dn = dc("sh", "-c", f"samba-tool user show fabric-sso-lan {' '.join(SMB)} | sed -n 's/^dn: //p'").stdout.strip()
ldif = f"dn: {dn}\nchangetype: modify\nreplace: msDS-SupportedEncryptionTypes\nmsDS-SupportedEncryptionTypes: 24\n"
print("AES only:", sh(["docker", "exec", "-i", DC, "ldbmodify", "-H", "/data/private/sam.ldb"], input=ldif).stdout.strip())
dc("rm", "-f", "/data/k1-sso.keytab")
for spn in (f"HTTP/{HOST}", f"HTTP/{CANON}"):
    dc("samba-tool", "domain", "exportkeytab", "/data/k1-sso.keytab", f"--principal={spn}@{AD_REALM}", *SMB)
# a domain person to sign in as, with a keytab of their own (kinit without a password on any command line)
dc("samba-tool", "user", "create", "kerb", "--random-password", "--given-name=Kerb", "--surname=T", *SMB, ok=False)
dc("samba-tool", "group", "addmembers", "lan-users", "kerb", *SMB, ok=False)
dc("rm", "-f", "/data/k1-kerb.keytab")
dc("samba-tool", "domain", "exportkeytab", "/data/k1-kerb.keytab", f"--principal=kerb@{AD_REALM}", *SMB)
print("kerb's UPN:", dc("sh", "-c", f"samba-tool user show kerb {' '.join(SMB)} | grep -i principal").stdout.strip())

# 2. Keycloak: the keytab and a krb5.conf mapping fabric's web domain to the AD realm
sh(["docker", "cp", f"{DC}:/data/k1-sso.keytab", f"{W}/sso.keytab"])
krb5 = (f"[libdefaults]\n  default_realm = {AD_REALM}\n  dns_lookup_kdc = false\n  rdns = false\n"
        f"[realms]\n  {AD_REALM} = {{\n    kdc = {DC_IP}\n  }}\n"
        f"[domain_realm]\n  .lan.j-j.family = {AD_REALM}\n  .ad.j-j.family = {AD_REALM}\n")
with open(f"{W}/krb5.conf", "w") as f:
    f.write(krb5)
sh(["docker", "cp", f"{W}/sso.keytab", f"{KC}:/opt/keycloak/conf/sso.keytab"])
sh(["docker", "cp", f"{W}/krb5.conf", f"{KC}:/etc/krb5.conf"])
sh(["docker", "exec", "-u", "0", KC, "chown", "1000", "/opt/keycloak/conf/sso.keytab"], ok=False)

kc = Admin(TLSClient(KC_IP, 8443, HOST, ROOT_CA), "admin", "KcAdmin1")
R = f"/{KC_REALM}"
ldap = next(c for c in kc.call("GET", f"{R}/components?type=org.keycloak.storage.UserStorageProvider")[1]
            if c["providerId"] == "ldap")
ldap["config"].update({"allowKerberosAuthentication": ["true"], "kerberosRealm": [AD_REALM],
                       "serverPrincipal": [os.environ.get("K1_PRINCIPAL", "*")],
                       "keyTab": ["/opt/keycloak/conf/sso.keytab"], "useKerberosForPasswordAuthentication": ["false"],
                       "debug": ["true"]})
print("LDAP provider updated:", kc.call("PUT", f"{R}/components/{ldap['id']}", ldap)[0])
execs = kc.call("GET", f"{R}/authentication/flows/browser/executions")[1]
krb = next(e for e in execs if e.get("providerId") == "auth-spnego")
krb["requirement"] = "ALTERNATIVE"
kc.call("PUT", f"{R}/authentication/flows/browser/executions", krb)
print("browser flow: Kerberos", next(e for e in kc.call("GET", f"{R}/authentication/flows/browser/executions")[1]
                                     if e.get("providerId") == "auth-spnego")["requirement"])

# 3. a domain client: kinit from the person's keytab, then a browser-like request with Negotiate
sh(["docker", "cp", f"{DC}:/data/k1-kerb.keytab", f"{W}/kerb.keytab"])
sh(["cp", ROOT_CA, f"{W}/root_ca.crt"])
for p in os.listdir(W):
    os.chmod(os.path.join(W, p), 0o644)
AUTH = (f"/realms/{KC_REALM}/protocol/openid-connect/auth?client_id=account-console&response_type=code&scope=openid"
        f"&redirect_uri=https%3A%2F%2F{HOST}%2Frealms%2F{KC_REALM}%2Faccount%2F&state=s&nonce=n"
        "&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256")
client = f"""set -e
apt-get -qq update >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get -qq install -y krb5-user curl >/dev/null 2>&1
cp /w/krb5.conf /etc/krb5.conf
kinit -k -t /w/kerb.keytab kerb@{AD_REALM}
klist | sed -n 1,3p
neg() {{ curl -s -o /dev/null -w '%{{http_code}} %{{redirect_url}}\\n' --negotiate -u : --cacert /w/root_ca.crt \\
    --connect-to {HOST}:443:{KC_IP}:8443 "https://{HOST}{AUTH}" | cut -c1-140; }}
echo "== sso.<domain> asked by its own name"
neg
echo "== sso.<domain> as a CNAME of the host: the client canonicalizes (as Windows browsers do), asks for HTTP/{CANON}"
echo "{KC_IP} {CANON} {HOST}" >> /etc/hosts
sed -i 's/rdns = false/rdns = false\\n  dns_canonicalize_hostname = true/' /etc/krb5.conf
kdestroy; kinit -k -t /w/kerb.keytab kerb@{AD_REALM}
neg
klist | grep HTTP || true
kdestroy
echo "== without a ticket: the password form"
curl -s -w '\\n%{{http_code}}\\n' --cacert /w/root_ca.crt --connect-to {HOST}:443:{KC_IP}:8443 "https://{HOST}{AUTH}" \\
  | grep -oE 'name="password"|^[0-9]{{3}}$' | tr '\\n' ' '; echo
"""
res = sh(["docker", "run", "--rm", "--network", NET, "-v", f"{W}:/w:ro", "debian:trixie", "bash", "-c", client],
         ok=False)
print(res.stdout + res.stderr[-800:])
print("--- Keycloak's log (Kerberos)")
print("\n".join(ln for ln in sh(["docker", "logs", "--since", "3m", KC], ok=False).stdout.splitlines()
                if "erberos" in ln or "SPNEGO" in ln or "GSS" in ln)[-1500:])
