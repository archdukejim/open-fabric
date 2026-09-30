#!/usr/bin/env python3
"""FreeRADIUS 802.1X (optional, design §6) on fabric's image and templates,
against a real 389-DS seeded with fabric's schema and devices created by
fabric's own directory functions:

  EAP-TLS (eapol_test): a certificate linked to an enabled device whose role
  grants network:eap-tls is accepted with the role's VLAN (lowest priority
  wins); refused: a disabled device, an unlinked certificate, a role without
  the permission, a certificate from another CA; unlinking takes effect at
  once. MAB (radclient): a device's MAC with network:mab is accepted with its
  VLAN, without it refused. EAP-TTLS/PAP (people, eapol_test): members of a
  mapped group are accepted with the group's VLAN (lowest priority wins),
  refused: a wrong password, a locked account (the directory's lockout), a
  person in no mapped group, an unknown name, and a password sent outside
  the tunnel. Refused before any policy: an unknown RADIUS
  client, a wrong secret, a request without Message-Authenticator. The
  directory down -> refused (fail closed). Container hardening.

    sudo python3 tests/freeradius/run.py      (needs Docker, openssl, root)
"""
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests")
W = OUT + "/freeradius"
NET, SUBNET, GW = "radtest_net", "10.254.24.0/24", "10.254.24.1"
DS_IP, RADIUS_IP, SWITCH_IP, STRANGER_IP = "10.254.24.50", "10.254.24.98", "10.254.24.10", "10.254.24.11"
DOMAIN, BASE = "lan.j-j.family", "dc=lan,dc=j-j,dc=family"       # tests/render.py's install
SECRET = "Sw1tchSecretForTests0123456789ab"
FAILED = 0
sys.path[0:0] = [os.path.join(REPO, "fabricctl", "lib"), REPO]
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402
from fabriclib.pki.install_cert import install_cert  # noqa: E402
from fabriclib.radius.deploy_freeradius import deploy_freeradius  # noqa: E402
from fabriclib.radius.normalize_radius_clients import normalize_radius_clients  # noqa: E402
from fabriclib.radius.normalize_radius_people import normalize_radius_people  # noqa: E402
from fabriclib.ldap.ensure_default_device_roles import ensure_default_device_roles  # noqa: E402
from fabriclib.ldap.list_roles import list_roles  # noqa: E402
import fabriclib.ldap.add_device as add_device_mod  # noqa: E402
import fabriclib.ldap.add_role as add_role_mod  # noqa: E402
import fabriclib.ldap.common.run_dirsrv as run_dirsrv_mod  # noqa: E402
import fabriclib.ldap.link_device_cert as link_mod  # noqa: E402
import fabriclib.ldap.update_device as update_device_mod  # noqa: E402

# fabric's directory functions, pointed at the test directory; no audit log on this machine
run_dirsrv_mod.load_secrets = lambda: {"ldap_device_admin_password": "Da1"}
for m in (add_device_mod, add_role_mod, link_mod, update_device_mod):
    m.write_audit = lambda *a, **k: None
V = {"ldap_base_dn": BASE, "dirsrv_container": "rt-ds"}


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[-700:]}"))


def sh(cmd, ok=True, **kw):
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    if ok and res.returncode != 0:
        raise SystemExit(f"failed: {cmd}\n{res.stdout[-1500:]}{res.stderr[-1500:]}")
    return res


def until(pred, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(2)
    return False


def cleanup():
    sh("docker rm -f rt-ds rt-radius rt-switch rt-stranger >/dev/null 2>&1", ok=False)
    sh(f"docker network rm {NET} >/dev/null 2>&1", ok=False)


def openssl(*args):
    sh(["openssl", *args], cwd=f"{W}/pki")


def leaf(name, ca, eku="clientAuth", cn=None):
    """A key + certificate signed by `ca` (root/int/foreign); returns the SHA-256 fingerprint."""
    openssl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{name}.key", "-out", f"{name}.csr",
            "-subj", f"/CN={cn or name}")
    with open(f"{W}/pki/{name}.ext", "w") as f:
        f.write(f"extendedKeyUsage={eku}\n" + (f"subjectAltName=DNS:{cn}\n" if cn else ""))
    openssl("x509", "-req", "-in", f"{name}.csr", "-CA", f"{ca}.crt", "-CAkey", f"{ca}.key", "-CAcreateserial",
            "-out", f"{name}.crt", "-days", "2", "-extfile", f"{name}.ext")
    fp = sh(["openssl", "x509", "-in", f"{W}/pki/{name}.crt", "-noout", "-fingerprint", "-sha256"]).stdout
    return fp.strip().split("=", 1)[1].upper()


cleanup()
shutil.rmtree(W, ignore_errors=True)
os.makedirs(f"{W}/pki")
DEBIAN = read_images_lock(os.path.join(REPO, "fabricctl"))["debian"]["ref"]

# ------------------------------------------------------------------ images
build = sh(["docker", "build", "-q", "-t", "fabric/freeradius:test", "--build-arg", f"BASE_IMAGE={DEBIAN}",
            f"{REPO}/fabricctl/jinja/freeradius/build"], ok=False)
check("FreeRADIUS image builds from Debian's packages on the pinned base", build.returncode == 0, build.stderr)
if build.returncode:
    sys.exit(1)
version = sh("docker run --rm --entrypoint /usr/sbin/freeradius fabric/freeradius:test -v", ok=False).stdout
check("FreeRADIUS 3.2 inside", "FreeRADIUS Version 3.2." in version, version[:120])
sh(["docker", "build", "-q", "-t", "fabric/dirsrv:test", "--build-arg", f"BASE_IMAGE={DEBIAN}",
    "--build-arg", "DS_UID=911", "--build-arg", "DS_GID=911", f"{REPO}/fabricctl/jinja/dirsrv/build"])
os.makedirs(f"{W}/client-build")
with open(f"{W}/client-build/Dockerfile", "w") as f:        # the test's switch: eapol_test + radclient
    f.write("FROM fabric/freeradius:test\nUSER root\nRUN apt-get update && apt-get install -y "
            "--no-install-recommends eapoltest freeradius-utils && rm -rf /var/lib/apt/lists/*\n"
            'ENTRYPOINT ["sleep", "infinity"]\n')
sh(["docker", "build", "-q", "-t", "fabric/radius-client:test", f"{W}/client-build"])

# ------------------------------------------------------------------ PKI (a stand-in for fabric's Step-CA)
openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "root.key", "-out", "root.crt", "-days", "2",
        "-subj", "/CN=Test Root", "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign")
openssl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", "int.key", "-out", "int.csr", "-subj", "/CN=Test Int")
with open(f"{W}/pki/int.ext", "w") as f:
    f.write("basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n")
openssl("x509", "-req", "-in", "int.csr", "-CA", "root.crt", "-CAkey", "root.key", "-CAcreateserial",
        "-out", "int.crt", "-days", "2", "-extfile", "int.ext")
openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "foreign.key", "-out", "foreign.crt",
        "-days", "2", "-subj", "/CN=Foreign Root", "-addext", "basicConstraints=critical,CA:TRUE")
leaf("ldap", "int", "serverAuth,clientAuth", f"ldap.{DOMAIN}")
leaf("radius", "int", "serverAuth", f"radius.{DOMAIN}")
FP = {d: leaf(d, "int") for d in ("laptop1", "laptop2", "laptop3", "printer1", "cam1")}
FP["impostor"] = leaf("impostor", "foreign")
for name in ("ldap", "radius"):          # chains as Step-CA hands them out
    with open(f"{W}/pki/{name}.chain", "w") as f:
        f.write(open(f"{W}/pki/{name}.crt").read() + open(f"{W}/pki/int.crt").read())

# ------------------------------------------------------------------ 389-DS with fabric's seed
sh([sys.executable, f"{REPO}/tests/render.py", f"{W}/rendered"])
os.makedirs(f"{W}/ds/data/tls/ca")
os.makedirs(f"{W}/ds/seed")
shutil.copy(f"{W}/pki/ldap.crt", f"{W}/ds/data/tls/server.crt")
shutil.copy(f"{W}/pki/ldap.key", f"{W}/ds/data/tls/server.key")
for n in ("root.crt", "int.crt"):
    shutil.copy(f"{W}/pki/{n}", f"{W}/ds/data/tls/ca/{n}")
for n in os.listdir(f"{W}/rendered/dirsrv/seed"):
    shutil.copy(f"{W}/rendered/dirsrv/seed/{n}", f"{W}/ds/seed/{n}")
shutil.copy(f"{REPO}/fabricctl/jinja/dirsrv/seed.py", f"{W}/ds/seed/seed.py")
sh(f"chown -R 911:911 {W}/ds/data && chown -R 0:911 {W}/ds/seed && chmod 750 {W}/ds/seed && chmod 640 {W}/ds/seed/*")
sh(f"docker network create --subnet {SUBNET} --gateway {GW} {NET}")


def start_ds():
    sh(["docker", "run", "-d", "--name", "rt-ds", "--network", NET, "--ip", DS_IP, "--network-alias", f"ldap.{DOMAIN}",
        "--hostname", f"ldap.{DOMAIN}", "--user", "911:911", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "-e", f"DS_SUFFIX_NAME={BASE}", "-e", "DS_DM_PASSWORD=DmPass1",
        "-v", f"{W}/ds/data:/data", "-v", f"{W}/ds/seed:/seed:ro",
        "--health-cmd", "/usr/libexec/dirsrv/dscontainer -H", "--health-interval", "5s",
        "--health-start-period", "120s", "fabric/dirsrv:test"])
    return until(lambda: sh("docker inspect -f {{.State.Health.Status}} rt-ds", ok=False).stdout.strip() == "healthy",
                 240)


def seed():
    for _ in range(12):
        if sh("docker exec rt-ds sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF \"$DS_SUFFIX_NAME (\" "
              "|| dsconf localhost backend create --suffix \"$DS_SUFFIX_NAME\" --be-name userroot'", ok=False).returncode == 0:
            break
        time.sleep(5)
    return sh("docker exec rt-ds sh -c 'python3 /seed/seed.py /seed/*.ldif'", ok=False).stdout


check("389-DS starts with fabric's seed (radius_reader account included)", start_ds())
if "RESTART_REQUIRED" in seed():
    sh("docker restart rt-ds")
    until(lambda: sh("docker inspect -f {{.State.Health.Status}} rt-ds", ok=False).stdout.strip() == "healthy", 240)
    seed()

# setup's default device roles: created once; a deleted one is not brought back
marker = f"{W}/default-device-roles"
added = ensure_default_device_roles(V, marker, container="rt-ds")
roles = {r["name"]: r for r in list_roles(V)}
check("default device roles created (six, no VLANs), MAB ones only network:mab",
      sorted(added) == ["iot", "network-gear", "phones-tablets", "printers", "servers", "workstations"]
      and all(not r["vlan"] for r in roles.values()) and roles["printers"]["permissions"] == ["network:mab"]
      and "network:eap-tls" in roles["workstations"]["permissions"], (added, roles))
sh(["docker", "exec", "-i", "rt-ds", "python3", "-"], input=f"""
import ldap
c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
c.simple_bind_s("cn=super_admin,ou=admins,ou=accounts,{BASE}", "Sa1")
c.delete_s("cn=iot,ou=device-roles,{BASE}")
""")
again = ensure_default_device_roles(V, marker, container="rt-ds")
check("...a default role the admin deleted is not brought back on the next setup",
      again == [] and "iot" not in {r["name"] for r in list_roles(V)}, again)

# roles and devices, made by fabric's own directory functions
add_role_mod.add_role(V, "test", "staff", {"permissions": ["network:eap-tls"], "vlan": "20", "priority": 50})
add_role_mod.add_role(V, "test", "quarantine", {"permissions": ["network:eap-tls"], "vlan": "99", "priority": 10})
add_role_mod.add_role(V, "test", "mab-printers", {"permissions": ["network:mab"], "vlan": "30", "priority": 50})
add_role_mod.add_role(V, "test", "dns-only", {"permissions": ["dns:dhcp-register"], "priority": 50})
add_device_mod.add_device(V, "test", "laptop1", {"type": "laptop", "roles": ["staff"]})
add_device_mod.add_device(V, "test", "laptop2", {"type": "laptop", "roles": ["staff"], "enabled": False})
add_device_mod.add_device(V, "test", "laptop3", {"type": "laptop", "roles": ["staff", "quarantine"]})
add_device_mod.add_device(V, "test", "printer1", {"type": "printer", "roles": ["mab-printers"],
                                                  "macs": ["02:00:00:00:30:01"]})
add_device_mod.add_device(V, "test", "cam1", {"type": "camera", "roles": ["dns-only"], "macs": ["02:00:00:00:30:02"]})
for d in ("laptop1", "laptop2", "laptop3", "cam1"):          # printer1's certificate stays unlinked
    link_mod.link_device_cert(V, "test", d, FP[d])

# people and groups (as Keycloak writes them to 389-DS), made as the directory's super admin
PW = "Correct-Horse-9"
PEOPLE = {"alice": ["staff"], "gina": ["staff", "guests"], "sam": ["contractors"], "nora": ["sales"],
          "lockme": ["staff"]}
seed_people = f"""
import ldap, ldap.modlist
c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
c.simple_bind_s("cn=super_admin,ou=admins,ou=accounts,{BASE}", "Sa1")
people = {PEOPLE!r}
for uid in people:
    c.add_s("uid=%s,ou=users,ou=accounts,{BASE}" % uid, ldap.modlist.addModlist({{
        "objectClass": [b"top", b"person", b"organizationalPerson", b"inetOrgPerson"],
        "uid": [uid.encode()], "cn": [uid.encode()], "sn": [uid.encode()], "userPassword": [b"{PW}"]}}))
for group in sorted({{g for gs in people.values() for g in gs}}):
    members = [("uid=%s,ou=users,ou=accounts,{BASE}" % u).encode() for u, gs in people.items() if group in gs]
    c.add_s("cn=%s,ou=groups,{BASE}" % group, ldap.modlist.addModlist({{
        "objectClass": [b"top", b"groupOfNames"], "cn": [group.encode()], "member": members}}))
print("seeded")
"""
check("people and groups in the directory", "seeded" in sh(["docker", "exec", "-i", "rt-ds", "python3", "-"],
                                                           input=seed_people, ok=False).stdout)

# ------------------------------------------------------------------ FreeRADIUS from fabric's templates
clients, embedded = normalize_radius_clients([{"name": "switch1", "address": SWITCH_IP, "secret": SECRET}])
people_map = normalize_radius_people([{"group": "staff", "vlan": 20, "priority": 50},
                                      {"group": "guests", "vlan": 50, "priority": 60},
                                      {"group": "contractors", "priority": 70}])
rv = {"deploy_base_dir": W, "ldap_base_dn": BASE, "hostname_ldap": f"ldap.{DOMAIN}", "radius_clients": clients,
      "radius_people": people_map, "service_users": {"freeradius": {"uid": 916, "gid": 916}}}
deploy_freeradius(rv, {"radius_secrets": embedded, "ldap_radius_password": "Rr1"},
                  jinja_env(os.path.join(REPO, "fabricctl", "jinja")))
install_cert(f"{W}/pki/radius.chain", f"{W}/pki/radius.key", f"{W}/pki/root.crt", f"{W}/freeradius/certs", 916, 916,
             names=("server.pem", "server.key", None))
with open(f"{W}/freeradius/certs/ca.pem", "w") as f:       # as setup's certificate step writes it
    f.write(open(f"{W}/pki/root.crt").read() + open(f"{W}/pki/int.crt").read())
check("config: client secret root:freerad 0640, never world-readable",
      oct(os.stat(f"{W}/freeradius/config/clients.conf").st_mode & 0o777) == "0o640"
      and SECRET in open(f"{W}/freeradius/config/clients.conf").read())


def start_radius():
    sh(["docker", "run", "-d", "--name", "rt-radius", "--network", NET, "--ip", RADIUS_IP, "--user", "916:916",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--tmpfs", "/tmp:noexec,nosuid,size=8m", "--tmpfs", "/run/freeradius:uid=916,gid=916,mode=0700,size=8m",
        "-v", f"{W}/freeradius/config:/etc/freeradius/fabric:ro",
        "-v", f"{W}/freeradius/certs:/etc/freeradius/certs:ro",
        "-v", f"{W}/freeradius/python:/etc/freeradius/python:ro", "fabric/freeradius:test"])
    return until(lambda: "Ready to process requests" in logs(), 60)


def logs():
    res = sh("docker logs rt-radius", ok=False)
    return res.stdout + res.stderr


ready = start_radius()
check("FreeRADIUS starts on fabric's configuration (non-root, read-only)", ready, logs()[-1500:])
if not ready:
    cleanup()
    sys.exit(1)
for name, ip in (("rt-switch", SWITCH_IP), ("rt-stranger", STRANGER_IP)):
    sh(["docker", "run", "-d", "--name", name, "--network", NET, "--ip", ip, "-v", f"{W}/pki:/pki:ro",
        "fabric/radius-client:test"])


def eap_tls(cert, box="rt-switch", secret=SECRET, mac="02:00:00:00:10:01"):
    """(accepted, VLAN or None, output) for one EAP-TLS authentication."""
    conf = (f'network={{\n key_mgmt=IEEE8021X\n eap=TLS\n identity="{cert}"\n ca_cert="/pki/root.crt"\n'
            f' client_cert="/pki/{cert}.crt"\n private_key="/pki/{cert}.key"\n'
            f' domain_suffix_match="radius.{DOMAIN}"\n eapol_flags=0\n}}\n')
    res = sh(["docker", "exec", "-i", box, "sh", "-c",
              f"cat > /tmp/{cert}.conf && eapol_test -c /tmp/{cert}.conf -a {RADIUS_IP} -s '{secret}' "
              f"-M {mac} -t 10 -r 0"], ok=False, input=conf)
    text = res.stdout + res.stderr
    # eapol_test dumps the value in hex: "Value: 3230" is VLAN "20"
    vlan = re.search(r"Attribute 81 \(Tunnel-Private-Group-Id\).*?\n\s*Value: ([0-9a-fA-F]+)", text)
    vlan = bytes.fromhex(vlan.group(1)).decode() if vlan else None
    return res.returncode == 0 and "SUCCESS" in text, vlan, text


# radclient always adds a Message-Authenticator (since BlastRADIUS): a raw request without one
RAW_REQUEST = r'''
import hashlib, os, socket, sys
server, secret, mac = sys.argv[1], sys.argv[2].encode(), sys.argv[3].encode()
auth = os.urandom(16)
def attr(t, v):
    return bytes([t, len(v) + 2]) + v
pw, prev, enc = mac.ljust(32, b"\0"), auth, b""
for i in range(0, 32, 16):
    block = bytes(a ^ b for a, b in zip(pw[i:i + 16], hashlib.md5(secret + prev).digest()))
    enc, prev = enc + block, block
body = attr(1, mac) + attr(2, enc) + attr(31, mac) + attr(32, b"switch1")
packet = bytes([1, 7]) + (20 + len(body)).to_bytes(2, "big") + auth + body
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(4)
s.sendto(packet, (server, 1812))
try:
    print("Received", {2: "Access-Accept", 3: "Access-Reject"}.get(s.recv(4096)[0], "?"))
except socket.timeout:
    print("no reply")
'''


def mab(mac, box="rt-switch", secret=SECRET, authenticator=True, user=None, timeout=3):
    """(reply code or None, VLAN or None, output) for one MAB request (User-Name = the MAC)."""
    if not authenticator:
        res = sh(["docker", "exec", "-i", box, "python3", "-", RADIUS_IP, secret, mac], ok=False, input=RAW_REQUEST)
        code = re.search(r"Received (Access-\w+)", res.stdout)
        return code.group(1) if code else None, None, res.stdout + res.stderr
    attrs = (f'User-Name = "{user or mac}", User-Password = "{user or mac}", Calling-Station-Id = "{mac}", '
             f'NAS-Identifier = "switch1", Message-Authenticator = 0x00')
    res = sh(["docker", "exec", "-i", box, "radclient", "-x", "-r", "1", "-t", str(timeout), f"{RADIUS_IP}:1812",
              "auth", secret], ok=False, input=attrs + "\n")
    text = res.stdout + res.stderr
    code = re.search(r"Received (Access-\w+)", text)
    vlan = re.search(r'Tunnel-Private-Group-Id(?::\d+)? = "?(\d+)', text)
    return code.group(1) if code else None, vlan.group(1) if vlan else None, text


# ------------------------------------------------------------------ EAP-TLS
ok, vlan, out = eap_tls("laptop1")
check("EAP-TLS: linked certificate, enabled device, role grants it -> accepted on the role's VLAN (20)",
      ok and vlan == "20", out[-1200:] + logs()[-800:])
ok, vlan, out = eap_tls("laptop3")
check("EAP-TLS: two roles with VLANs -> the lowest priority number wins (quarantine, 99)", ok and vlan == "99",
      (vlan, out[-600:]))
ok, _, out = eap_tls("laptop2")
check("EAP-TLS: a disabled device is refused", not ok and "device=laptop2 reason=device_disabled" in logs(),
      logs()[-600:])
ok, _, out = eap_tls("printer1")
check("EAP-TLS: a fabric certificate linked to no device is refused",
      not ok and "reason=no_device_has_it" in logs(), logs()[-600:])
ok, _, out = eap_tls("cam1")
check("EAP-TLS: a device whose roles lack network:eap-tls is refused",
      not ok and "device=cam1 reason=no_role_grants_network:eap-tls" in logs(), logs()[-600:])
ok, _, out = eap_tls("impostor")
check("EAP-TLS: a certificate from another CA is refused in the TLS handshake", not ok, out[-400:])
link_mod.link_device_cert(V, "test", "laptop1", FP["laptop1"], link=False)
ok, _, out = eap_tls("laptop1")
check("EAP-TLS: unlinking the certificate refuses it at the next authentication",
      not ok and f"REJECT method=eap-tls device=- reason=no_device_has_it" in logs()
      and f"sha256={FP['laptop1']}" in logs().rsplit("REJECT method=eap-tls", 1)[-1], logs()[-400:])
link_mod.link_device_cert(V, "test", "laptop1", FP["laptop1"])

# ------------------------------------------------------------------ EAP-TTLS (people)
def eap_ttls(user, password, mac="02:00:00:00:20:01"):
    """(accepted, VLAN or None, output) for one EAP-TTLS/PAP login."""
    conf = (f'network={{\n key_mgmt=IEEE8021X\n eap=TTLS\n identity="{user}"\n anonymous_identity="anonymous"\n'
            f' password="{password}"\n phase2="auth=PAP"\n ca_cert="/pki/root.crt"\n'
            f' domain_suffix_match="radius.{DOMAIN}"\n eapol_flags=0\n}}\n')
    res = sh(["docker", "exec", "-i", "rt-switch", "sh", "-c",
              f"cat > /tmp/ttls.conf && eapol_test -c /tmp/ttls.conf -a {RADIUS_IP} -s '{SECRET}' -M {mac} -t 10 -r 0"],
             ok=False, input=conf)
    text = res.stdout + res.stderr
    vlan = re.search(r"Attribute 81 \(Tunnel-Private-Group-Id\).*?\n\s*Value: ([0-9a-fA-F]+)", text)
    return res.returncode == 0 and "SUCCESS" in text, bytes.fromhex(vlan.group(1)).decode() if vlan else None, text


ok, vlan, out = eap_ttls("alice", PW)
check("EAP-TTLS: a member of a mapped group, right password -> accepted on the group's VLAN (20)",
      ok and vlan == "20" and "ACCEPT method=eap-ttls person=alice group=staff vlan=20" in logs(),
      out[-800:] + logs()[-600:])
ok, vlan, out = eap_ttls("gina", PW)
check("EAP-TTLS: in two mapped groups -> the lowest priority number wins (staff, 20)", ok and vlan == "20",
      (vlan, logs()[-300:]))
ok, vlan, out = eap_ttls("sam", PW)
check("EAP-TTLS: a mapped group without a VLAN -> accepted on the port's default", ok and vlan is None,
      (vlan, logs()[-300:]))
ok, _, out = eap_ttls("alice", "wrong-password")
check("EAP-TTLS: a wrong password is refused", not ok and "person=alice reason=wrong_password_or_account_locked"
      in logs(), logs()[-400:])
ok, _, out = eap_ttls("nora", PW)
check("EAP-TTLS: a person in no mapped group is refused",
      not ok and "person=nora reason=in_no_group_mapped_for_802.1X" in logs(), logs()[-400:])
ok, _, out = eap_ttls("nobody", PW)
check("EAP-TTLS: an unknown name is refused", not ok and "person=nobody reason=no_such_person" in logs(),
      logs()[-400:])
for _ in range(5):
    eap_ttls("lockme", "wrong-password")
ok, _, out = eap_ttls("lockme", PW)
check("EAP-TTLS: after 5 wrong passwords the directory locks the account: the right one is refused too", not ok,
      logs()[-400:])
code, _, out = mab("02:00:00:00:30:01", user="alice")
check("a person's password sent outside the TLS tunnel (plain PAP) is refused", code == "Access-Reject", out[-300:])

# ------------------------------------------------------------------ MAB
code, vlan, out = mab("02-00-00-00-30-01")
check("MAB: a MAC whose device has network:mab -> Access-Accept on its VLAN (30)",
      code == "Access-Accept" and vlan == "30", out[-800:] + logs()[-600:])
code, _, out = mab("02:00:00:00:30:02")
check("MAB: a device without network:mab is refused", code == "Access-Reject", out[-400:])
code, _, out = mab("02:00:00:00:99:99")
check("MAB: an unknown MAC is refused", code == "Access-Reject", out[-400:])
code, _, out = mab("02:00:00:00:30:01", user="alice")
check("MAB: a User-Name that is not the calling MAC is refused", code == "Access-Reject", out[-400:])

# ------------------------------------------------------------------ refused before any policy
code, _, out = mab("02:00:00:00:30:01", box="rt-stranger")
check("an address that is not a RADIUS client gets no answer", code is None, out[-300:])
code, _, out = mab("02:00:00:00:30:01", secret="WrongSecretWrongSecret")
check("a wrong shared secret gets no Access-Accept", code != "Access-Accept", out[-300:])
code, _, out = mab("02:00:00:00:30:01", authenticator=False)
check("a request without Message-Authenticator is dropped (BlastRADIUS)",
      code is None and "Message-Authenticator" in logs(), out[-300:] + logs()[-400:])

# ------------------------------------------------------------------ fail closed
sh("docker stop rt-ds")
code, _, out = mab("02:00:00:00:30:01", timeout=12)
check("389-DS down: refused, not let in (fail closed)",
      code == "Access-Reject" and "reason=directory_error" in logs(), out[-300:] + logs()[-400:])
sh("docker start rt-ds")
until(lambda: sh("docker inspect -f {{.State.Health.Status}} rt-ds", ok=False).stdout.strip() == "healthy", 240)
code, _, out = mab("02:00:00:00:30:01")
check("389-DS back: FreeRADIUS reconnects by itself", code == "Access-Accept", out[-300:] + logs()[-400:])

# ------------------------------------------------------------------ hardening
import json  # noqa: E402
h = json.loads(sh("docker inspect rt-radius").stdout)[0]
check("container: uid 916, no capabilities, read-only, no-new-privileges",
      h["Config"]["User"] == "916:916" and h["HostConfig"]["CapDrop"] == ["ALL"] and not h["HostConfig"].get("CapAdd")
      and h["HostConfig"]["ReadonlyRootfs"] and "no-new-privileges:true" in h["HostConfig"]["SecurityOpt"])
check("no RADIUS secret and no person's password in the logs",
      SECRET not in logs() and PW not in logs() and "wrong-password" not in logs())

cleanup()
print(f"\n{'FAILED' if FAILED else 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
