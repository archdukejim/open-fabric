"""The `samba` suite, real containers (manual 2.11.2.13, S1.3): a DC from fabric's image, run as the rendered compose
file runs it (on a private test network instead of the host's: WSL is shared with other environments), its files
written by the real deploy_samba, the domain converged by the real converge_domain — twice, the second changing
nothing — and the refusals: a site admin in another site, a password the policy refuses, a wrong password.
    sudo python3 tests/samba/dc.py
"""
import json
import os
import shlex
import shutil
import subprocess
import sys

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402
from fabriclib.samba.converge_domain import converge_domain  # noqa: E402
from fabriclib.samba.deploy_samba import deploy_samba  # noqa: E402
from fabriclib.samba.write_bind_dlz import write_bind_dlz  # noqa: E402
from fabriclib.secrets.random_password import random_password  # noqa: E402

W = os.path.join(os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests"), "samba")
NET, SUBNET, IP = "sambatest_net", "10.254.30.0/24", "10.254.30.10"
# BIND shares the DC's address, as both share the host's on an install (the AD zone sends updates to the DC's name)
BIND_IP = IP
DC, IMAGE, BIND = "sambatest-dc", "fabric/samba:test", "sambatest-bind"
CLIENT = IMAGE                  # the DC's image has dig and nsupdate (bind9-dnsutils)
BASE = "DC=ad,DC=lan,DC=test"
POLICY = {"minimum_length": 14, "complexity": True, "history": 24, "minimum_age_days": 0, "maximum_age_days": 0,
          "lockout_threshold": 5, "lockout_minutes": 15, "lockout_window_minutes": 15}
PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {str(detail)[:400]}")


def sh(cmd, ok=True, **kw):
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    if ok and res.returncode:
        raise RuntimeError(f"{cmd}: {res.stderr.strip()[-400:]}")
    return res


def cleanup():
    sh(["docker", "rm", "-f", DC, BIND, "sambatest-rodc"], ok=False)
    sh(["docker", "network", "rm", NET], ok=False)


def dc(*args, stdin=None):
    return sh(["docker", "exec", "-i", DC, *args], ok=False, input=stdin)


def as_user(user, password, tool, ldif=None):
    """Run an ldb tool against the DC over LDAP as a user, from a throwaway container (the DC's image): ldbadd or
    ldbmodify with an LDIF, or (ldif None) ldbsearch of the domain's base, which needs a successful sign-in."""
    auth = os.path.join(W, f"{user}.auth")
    with open(auth, "w") as f:
        f.write(f"username={user}\npassword={password}\ndomain=AD\n")
    os.chmod(auth, 0o600)
    with open(os.path.join(W, "op.ldif"), "w") as f:
        f.write(ldif or "")
    what = ["/op.ldif"] if ldif is not None else ["-b", BASE, "-s", "base", "dn"]
    return sh(["docker", "run", "--rm", "--network", NET, "-v", f"{auth}:/auth:ro", "-v", f"{W}/op.ldif:/op.ldif:ro",
               "--entrypoint", tool, IMAGE, "-H", f"ldap://{IP}", "-A", "/auth", *what], ok=False)


cleanup()
shutil.rmtree(W, ignore_errors=True)
os.makedirs(os.path.join(W, "stepca", "data", "certs"))
DEBIAN = read_images_lock(os.path.join(REPO, "config"))["debian"]["ref"]
# the build folder as a host has it: install_service_units copies it with plain modes (files 0644)
context = os.path.join(W, "build")
shutil.copytree(f"{REPO}/packaging/images/samba", context)
for name in os.listdir(context):
    os.chmod(os.path.join(context, name), 0o644)
build = sh(["docker", "build", "-q", "-t", IMAGE, "--build-arg", f"BASE_IMAGE={DEBIAN}", context], ok=False)
check("the DC image builds from Debian's packages on the pinned base", build.returncode == 0, build.stderr)
if build.returncode:
    sys.exit(1)

# the settings and compose file as an install renders them
env = jinja_env(os.path.join(REPO, "templates"))
v = yaml.safe_load(env.get_template("vars.yaml.j2").render(
    domain="lan.test", hostname="dc1", host_ip=IP, lan_cidr=SUBNET, lan_gateway="10.254.30.1", site_name="lan",
    ad_domain="ad.lan.test", ad_password_policy=POLICY, deploy_base_dir=W))
compose = yaml.safe_load(env.get_template("samba/docker-compose.yml.j2").render(**v))["services"]["samba"]
# a stand-in for fabric's Step-CA: the DC's certificate and the root CA the trust GPO carries
pki = os.path.join(W, "stepca", "data", "certs")
sh(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{pki}/root.key", "-out",
    f"{pki}/root_ca.crt", "-days", "2", "-subj", "/CN=Test Root"])
deploy_samba(v, {"ad_admin_password": random_password()}, env)
tls = os.path.join(W, "samba", "tls")
shutil.copy(f"{pki}/root_ca.crt", f"{tls}/root_ca.crt")
sh(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{tls}/privkey.pem", "-out",
    f"{tls}/fullchain.pem", "-days", "2", "-subj", f"/CN={v['hostname_dc']}"])
os.chmod(f"{tls}/privkey.pem", 0o600)
admin_pw = open(os.path.join(W, "samba", "secrets", "admin_password")).read().strip()
check("deploy_samba: the DC's resolver is the host's address",
      open(os.path.join(W, "samba", "resolv.conf")).read().startswith(f"nameserver {IP}\n"))
check("deploy_samba: root-only folders (data traversable: SYSVOL is served as each user), the password file "
      "0600, the converge code copied",
      all(os.stat(os.path.join(W, "samba", d)).st_mode & 0o077 == 0 for d in ("secrets", "converge"))
      and os.stat(os.path.join(W, "samba", "data")).st_mode & 0o777 == 0o755
      and os.stat(os.path.join(W, "samba", "secrets", "admin_password")).st_mode & 0o777 == 0o600
      and os.path.exists(os.path.join(W, "samba", "converge", "converge.py")))

# run it as the compose file says, on the test network
sh(["docker", "network", "create", "--subnet", SUBNET, NET])
run = ["docker", "run", "-d", "--name", DC, "--hostname", "dc1", "--network", NET, "--ip", IP,
       "--read-only", "--memory", compose["mem_limit"], "--cap-drop", "ALL"]
run += [x for c in compose["cap_add"] for x in ("--cap-add", c)]
run += [x for o in compose["security_opt"] for x in ("--security-opt", o)]
run += [x for t in compose["tmpfs"] for x in ("--tmpfs", t)]
run += [x for k, val in compose["environment"].items() for x in ("-e", f"{k}={val}")]
run += [x for m in compose["volumes"] for x in ("-v", m)]
run += ["--health-cmd", shlex.join(compose["healthcheck"]["test"][1:]), "--health-interval", "10s",
        "--health-start-period", "180s", IMAGE]
sh(run)
health = ""
for _ in range(60):
    health = sh(["docker", "inspect", "-f", "{{.State.Health.Status}}", DC], ok=False).stdout.strip()
    if health == "healthy":
        break
    sh("sleep 5")
check("the DC provisions and turns healthy", health == "healthy", sh(["docker", "logs", DC], ok=False).stdout[-800:])
if health != "healthy":
    cleanup()
    sys.exit(1)
check("provisioning prints no password (only that one was set)",
      all("password set for" in line for line in sh(["docker", "logs", DC], ok=False).stdout.lower().splitlines()
          if "password" in line))
info = json.loads(sh(["docker", "inspect", DC]).stdout)[0]["HostConfig"]
check("hardened as rendered: exactly the six capabilities, read-only, no-new-privileges, a memory limit",
      sorted(info["CapAdd"]) == ["CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_FOWNER", "CAP_NET_BIND_SERVICE", "CAP_SETGID",
                                 "CAP_SETUID"]
      and info["CapDrop"] == ["ALL"] and info["ReadonlyRootfs"] and "no-new-privileges:true" in info["SecurityOpt"]
      and info["Memory"] > 0, info["CapAdd"])

first = converge_domain(v, os.path.join(W, "federation.yaml"), container=DC)
check("converge: schema, layout, groups, access, AD site, policy and GPOs made", len(first) > 30, first)
again = converge_domain(v, os.path.join(W, "federation.yaml"), container=DC)
check("converge again changes nothing (idempotent)", again == [], again)
ous = dc("ldbsearch", "-H", "/data/private/sam.ldb", "-b", f"OU=sites,{BASE}", "(objectClass=organizationalUnit)",
         "dn").stdout
check("the site's OU tree under OU=sites, with OU=organisation at the root site",
      ous.count("dn: ") == 14 and f"OU=organisation,OU=lan,OU=sites,{BASE}" in ous, ous.count("dn: "))
check("the directory is consistent (dbcheck)", "(0 errors)" in dc("samba-tool", "dbcheck", "-s", "/data/etc/smb.conf",
                                                                  "--cross-ncs").stdout)
policy = dc("samba-tool", "domain", "passwordsettings", "show", "-s", "/data/etc/smb.conf").stdout
check("the admin's password policy is the domain's",
      "Minimum password length: 14" in policy and "Password complexity: on" in policy
      and "Account lockout threshold (attempts): 5" in policy, policy)
gpos = dc("samba-tool", "gpo", "listall", "-H", "/data/private/sam.ldb", "-s", "/data/etc/smb.conf").stdout
check("the trust GPO and the site's log-on GPO exist", "fabric: trust in fabric's root CA" in gpos
      and "fabric: lan log-on rights" in gpos, gpos)
files = dc("find", "/data/state/sysvol", "-name", "Registry.pol", "-o", "-name", "GptTmpl.inf").stdout
check("their files are in SYSVOL (Registry.pol, GptTmpl.inf)", "Registry.pol" in files and "GptTmpl.inf" in files)
inf_path = next(x for x in files.splitlines() if x.endswith("GptTmpl.inf"))
inf = subprocess.run(["docker", "exec", DC, "cat", inf_path], capture_output=True).stdout     # UTF-16: bytes
check("the log-on policy names the site's groups and each machine's local Administrators (never lock out)",
      "S-1-5-32-544".encode("utf-16-le") in inf and "SeInteractiveLogonRight".encode("utf-16-le") in inf)

# BIND serves the AD zone from the DC's database through DLZ (manual 2.11.2.6, Q2): fabric's BIND image with the
# files write_bind_dlz makes, mounted as the rendered compose file mounts them; a minimal named.conf around them
check("before the domain exists BIND's DLZ files load nothing", "not provisioned" in open(
    os.path.join(W, "samba", "bind", "dlz.conf")).read())
check("once provisioned, write_bind_dlz turns DLZ on (BIND must restart)", write_bind_dlz(v) is True)
check("and again changes nothing", write_bind_dlz(v) is False)
bind_build = sh(["docker", "build", "-q", "-t", "fabric/bind9:samba-test", "--build-arg", f"BASE_IMAGE={DEBIAN}",
                 f"{REPO}/packaging/images/bind9"], ok=False)
check("fabric's BIND image (with Samba's DLZ libraries) builds", bind_build.returncode == 0, bind_build.stderr)
etc_bind = os.path.join(W, "bindtest")
os.makedirs(etc_bind)
with open(os.path.join(etc_bind, "named.conf"), "w") as f:
    f.write('options {\n directory "/var/cache/bind";\n listen-on port 53 { any; };\n listen-on-v6 { none; };\n'
            ' recursion no;\n allow-query { any; };\n include "/etc/bind-samba/options.conf";\n};\n'
            'zone "lan.test" { type primary; file "/etc/bind/db.lan.test"; };\n'
            'include "/etc/bind-samba/dlz.conf";\n')
with open(os.path.join(etc_bind, "db.lan.test"), "w") as f:
    f.write("$TTL 300\n@ IN SOA ns.lan.test. admin.lan.test. 1 3600 600 86400 300\n@ IN NS ns.lan.test.\n"
            "ns IN A 10.254.30.10\nweb IN A 10.254.30.20\n")
for name in os.listdir(etc_bind):
    os.chmod(os.path.join(etc_bind, name), 0o644)
os.chmod(etc_bind, 0o755)
bind_compose = yaml.safe_load(env.get_template("bind9/docker-compose.yml.j2").render(**v))["services"]["bind9"]
samba_mounts = [m for m in bind_compose["volumes"]
                if m.split(":")[1] in ("/etc/bind-samba", "/data/bind-dns", "/etc/samba")]
sh(["docker", "run", "-d", "--name", BIND, "--network", f"container:{DC}", "--user", "600:600", "--read-only",
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--memory", "128m",
    "--tmpfs", "/run/named:uid=600,gid=600,mode=0755,size=4m", "--tmpfs", "/tmp:size=8m",
    "--tmpfs", "/var/cache/bind:uid=600,gid=600,size=8m"]
   + [x for t in bind_compose["tmpfs"] if t.startswith("/var/tmp") for x in ("--tmpfs", t)]
   + [x for m in samba_mounts for x in ("-v", m)] + ["-v", f"{etc_bind}:/etc/bind:ro", "fabric/bind9:samba-test"])
sh("sleep 8")


def client(*args):
    return sh(["docker", "run", "--rm", "--network", NET, "--entrypoint", args[0], CLIENT, *args[1:]], ok=False)


def unsigned_update(zone):
    """An nsupdate with no key: BIND must refuse it in every zone."""
    with open(os.path.join(W, "upd"), "w") as f:
        f.write(f"server {BIND_IP}\nzone {zone}\nupdate add evil.{zone} 60 A 10.254.30.66\nsend\n")
    return sh(["docker", "run", "--rm", "--network", NET, "-v", f"{W}/upd:/upd:ro", "--entrypoint", "nsupdate",
               CLIENT, "/upd"], ok=False)


srv = client("dig", "+short", f"@{BIND_IP}", "SRV", "_ldap._tcp.ad.lan.test").stdout
check("BIND answers the AD zone from the DC's database (DLZ)", "389 dc1.ad.lan.test." in srv,
      sh(["docker", "logs", BIND], ok=False).stderr[-600:])
check("and fabric's own zone, unchanged", client("dig", "+short", f"@{BIND_IP}", "A", "web.lan.test").stdout.strip()
      == "10.254.30.20")
upd = dc("samba_dnsupdate", "-s", "/data/etc/smb.conf", "--all-names")
check("the DC's signed (GSS-TSIG) updates are accepted through BIND",
      upd.returncode == 0 and "Failed update" not in upd.stdout + upd.stderr, (upd.stdout + upd.stderr)[-400:])
evil = unsigned_update("ad.lan.test")
check("refused: an unsigned update to the AD zone", "REFUSED" in evil.stdout + evil.stderr, evil.stderr[-200:])
evil = unsigned_update("lan.test")
check("refused: an unsigned update to fabric's zone", "REFUSED" in evil.stdout + evil.stderr, evil.stderr[-200:])
bind_info = json.loads(sh(["docker", "inspect", BIND]).stdout)[0]
check("BIND still runs as its own user with no capabilities", bind_info["Config"]["User"] == "600:600"
      and not bind_info["HostConfig"]["CapAdd"] and bind_info["State"]["Running"])

# refusals: a site's admin writes its own site only (Q4), the policy is enforced
lab = {"site": "lab", "root": False, "password_policy": POLICY, "networks": [],
       "root_ca_pem": open(f"{pki}/root_ca.crt").read()}
res = dc("python3", "/fabric/converge.py", stdin=json.dumps(lab))
check("a second site's OU, groups and access entries", res.returncode == 0 and "group lab-admins created" in res.stdout,
      res.stderr)
lab_pw = random_password(20)
made = dc("samba-tool", "user", "create", "labadmin", lab_pw, "--userou=OU=people,OU=lab,OU=sites",
          "-s", "/data/etc/smb.conf")
dc("samba-tool", "group", "addmembers", "lab-admins", "labadmin", "-s", "/data/etc/smb.conf")
check("a lab admin is created", made.returncode == 0, made.stderr)
user = "dn: CN={0},OU=people,OU={1},OU=sites,%s\nobjectClass: user\nsAMAccountName: {0}\n" % BASE
own = as_user("labadmin", lab_pw, "ldbadd", user.format("labuser", "lab"))
check("a site admin adds a person in its own site", "successfully" in own.stdout + own.stderr, own.stderr)
other = as_user("labadmin", lab_pw, "ldbadd", user.format("intruder", "lan"))
share = sh(["docker", "run", "--rm", "--network", NET, "-v", f"{W}/labadmin.auth:/auth:ro", "--entrypoint",
            "smbclient", IMAGE, f"//{IP}/sysvol", "-A", "/auth", "-c",
            "ls ad.lan.test/Policies/{31B2F340-016D-11D2-945F-00C04FB984F9}/*"], ok=False)
check("an ordinary domain user reads SYSVOL (Group Policy reads it as the machine; found on host-1, S1.7)",
      share.returncode == 0 and "GPT.INI" in share.stdout.upper(), (share.stdout + share.stderr)[-300:])
check("refused: a site admin adding a person in another site", "successfully" not in other.stdout + other.stderr)
svc = as_user("labadmin", lab_pw, "ldbadd",
              f"dn: CN=svc,OU=service-accounts,OU=lab,OU=sites,{BASE}\nobjectClass: user\nsAMAccountName: svc\n")
check("refused: a site admin adding to its site's service accounts", "successfully" not in svc.stdout + svc.stderr)
domain = as_user("labadmin", lab_pw, "ldbmodify",
                 f"dn: CN=Administrator,CN=Users,{BASE}\nchangetype: modify\nreplace: description\ndescription: x\n")
check("refused: a site admin changing the domain's Administrator", "successfully" not in domain.stdout + domain.stderr)
short = dc("samba-tool", "user", "create", "shorty", "Ab1shortpw", "-s", "/data/etc/smb.conf")
check("refused: a password shorter than the policy's minimum", short.returncode != 0)
wrong = as_user("labadmin", lab_pw + "x", "ldbsearch")
check("refused: a wrong password", wrong.returncode != 0 and BASE not in wrong.stdout, wrong.stdout[-200:])
admin = as_user("Administrator", admin_pw, "ldbsearch")
check("the Administrator signs in with fabric's generated password", admin.returncode == 0 and BASE in admin.stdout,
      admin.stderr)

# a read-only DC joining with fabric's image (its join path), and NTLM at it for an account it does not cache:
# forwarded to the writable DC while it is up (the Q6 follow-up S1 owes: PEAP at an RODC site relies on it); with the
# writable DC down, cached accounts only, and no writes (manual 1.8.8.3)
RODC, RODC_IP = "sambatest-rodc", "10.254.30.12"
rw = os.path.join(W, "rodc")
for sub in ("data", "secrets"):
    os.makedirs(os.path.join(rw, sub), mode=0o700)
with open(os.path.join(rw, "secrets", "join.auth"), "w") as f:
    f.write(f"username=Administrator\npassword={admin_pw}\ndomain=AD\n")
os.chmod(os.path.join(rw, "secrets", "join.auth"), 0o600)
renv = {**compose["environment"], "HOST_NAME": "rodc1", "HOST_IP": RODC_IP, "INTERFACES": f"127.0.0.1 {RODC_IP}",
        "JOIN_ROLE": "RODC", "JOIN_SERVER": "dc1.ad.lan.test"}
rrun = ["docker", "run", "-d", "--name", RODC, "--hostname", "rodc1", "--network", NET, "--ip", RODC_IP,
        "--dns", IP, "--read-only", "--memory", compose["mem_limit"], "--cap-drop", "ALL"]
rrun += [x for c in compose["cap_add"] for x in ("--cap-add", c)]
rrun += [x for o in compose["security_opt"] for x in ("--security-opt", o)]
rrun += [x for t in compose["tmpfs"] for x in ("--tmpfs", t)]
rrun += [x for k, val in renv.items() for x in ("-e", f"{k}={val}")]
rrun += ["-v", f"{rw}/data:/data", "-v", f"{rw}/secrets:/run/secrets:ro", "-v", f"{W}/samba/tls:/tls:ro",
         "--health-cmd", shlex.join(compose["healthcheck"]["test"][1:]), "--health-interval", "10s",
         "--health-start-period", "180s", IMAGE]
sh(rrun)
rhealth = ""
for _ in range(60):
    rhealth = sh(["docker", "inspect", "-f", "{{.State.Health.Status}}", RODC], ok=False).stdout.strip()
    if rhealth in ("healthy", ""):
        break
    sh("sleep 5")
rlog = sh(["docker", "logs", RODC], ok=False)
check("an RODC joins with fabric's image (hardened like the DC) and turns healthy",
      rhealth == "healthy" and "joined" in rlog.stdout, (rlog.stdout + rlog.stderr)[-600:])
rep = sh(["docker", "exec", RODC, "ldbsearch", "-H", "/data/private/sam.ldb", "-b", f"OU=lan,OU=sites,{BASE}",
          "-s", "base", "dn"], ok=False).stdout
check("the domain, its layout and fabric's schema replicated to the RODC", f"OU=lan,OU=sites,{BASE}" in rep)


def ntlm_at_rodc(user, password):
    """An NTLM-only sign-in (Kerberos off) at the RODC over LDAP: its search of the base succeeds or fails."""
    auth = os.path.join(W, f"{user}-ntlm.auth")
    with open(auth, "w") as f:
        f.write(f"username={user}\npassword={password}\ndomain=AD\n")
    os.chmod(auth, 0o600)
    res = sh(["docker", "run", "--rm", "--network", NET, "-v", f"{auth}:/auth:ro", "--entrypoint", "ldbsearch", IMAGE,
              "-H", f"ldap://{RODC_IP}", "-A", "/auth", "--use-kerberos=off", "-b", BASE, "-s", "base", "dn"],
             ok=False)
    return res.returncode == 0 and BASE in res.stdout


check("NTLM at the RODC for an account it does not cache is forwarded to the writable DC (Q6 follow-up)",
      ntlm_at_rodc("labadmin", lab_pw))
cached_pw = random_password(20)
dc("samba-tool", "user", "create", "cachy", cached_pw, "--userou=OU=people,OU=lab,OU=sites", "-s", "/data/etc/smb.conf")
dc("samba-tool", "group", "addmembers", "Allowed RODC Password Replication Group", "cachy", "-s", "/data/etc/smb.conf")
pre = sh(["docker", "exec", RODC, "samba-tool", "rodc", "preload", "cachy", "-s", "/data/etc/smb.conf",
          "--server=dc1.ad.lan.test"], ok=False)
check("a site person's password is preloaded at the RODC", pre.returncode == 0, pre.stderr[-300:])
sh(["docker", "stop", DC])
check("with the writable DC down: a cached person signs in at the RODC", ntlm_at_rodc("cachy", cached_pw))
check("with the writable DC down: refused, the Administrator (never cached)", not ntlm_at_rodc("Administrator",
                                                                                               admin_pw))
check("with the writable DC down: refused, a person the RODC does not cache", not ntlm_at_rodc("labadmin", lab_pw))
with open(os.path.join(W, "op.ldif"), "w") as f:
    f.write(f"dn: CN=cachy,OU=people,OU=lab,OU=sites,{BASE}\nchangetype: modify\nreplace: description\n"
            "description: written at the RODC\n")
wr = sh(["docker", "run", "--rm", "--network", NET, "-v", f"{W}/cachy-ntlm.auth:/auth:ro", "-v",
         f"{W}/op.ldif:/op.ldif:ro", "--entrypoint", "ldbmodify", IMAGE, "-H", f"ldap://{RODC_IP}", "-A", "/auth",
         "--use-kerberos=off", "/op.ldif"], ok=False)
check("refused: a write at the RODC", "successfully" not in wr.stdout + wr.stderr, wr.stdout[-200:])
rinfo = json.loads(sh(["docker", "inspect", RODC]).stdout)[0]["HostConfig"]
check("the RODC is hardened like the DC (the six capabilities, read-only, a limit)",
      len(rinfo["CapAdd"]) == 6 and rinfo["ReadonlyRootfs"] and rinfo["Memory"] > 0)
print("RODC memory: " + sh(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", RODC], ok=False).stdout.strip())

if not os.environ.get("SAMBA_TEST_KEEP"):        # keep the containers to look into a failure
    cleanup()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
