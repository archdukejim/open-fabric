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
from fabriclib.secrets.random_password import random_password  # noqa: E402

W = os.path.join(os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests"), "samba")
NET, SUBNET, IP = "sambatest_net", "10.254.30.0/24", "10.254.30.10"
DC, IMAGE = "sambatest-dc", "fabric/samba:test"
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
    sh(["docker", "rm", "-f", DC], ok=False)
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
build = sh(["docker", "build", "-q", "-t", IMAGE, "--build-arg", f"BASE_IMAGE={DEBIAN}",
            f"{REPO}/packaging/images/samba"], ok=False)
check("the DC image builds from Debian's packages on the pinned base", build.returncode == 0, build.stderr)
if build.returncode:
    sys.exit(1)

# the settings and compose file as an install renders them
env = jinja_env(os.path.join(REPO, "templates"))
v = yaml.safe_load(env.get_template("vars.yaml.j2").render(
    domain="lan.test", hostname="dc1", host_ip=IP, lan_cidr=SUBNET, lan_gateway="10.254.30.1", site_name="lan",
    install_samba=True, ad_domain="ad.lan.test", ad_password_policy=POLICY, deploy_base_dir=W))
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
check("deploy_samba: root-only folders, the password file 0600, the converge code copied",
      all(os.stat(os.path.join(W, "samba", d)).st_mode & 0o077 == 0 for d in ("data", "secrets", "converge"))
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
check("hardened as rendered: exactly the five capabilities, read-only, no-new-privileges, a memory limit",
      sorted(info["CapAdd"]) == ["CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_FOWNER", "CAP_SETGID", "CAP_SETUID"]
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

cleanup()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
