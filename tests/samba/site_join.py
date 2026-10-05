"""The `samba` suite, sites joining the root's domain (manual 1.8.8.4, 2.11.2.22 S8.1-S8.2): a root DC (with BIND
serving the AD zone), and a site DC, writable, then another read-only, joining it the way a site's setup does — the
root prepares each site in its domain (prepare_site: OU, groups, service accounts, ACLs, id block, networks, a join
account that expires), the site's deploy_samba writes the join credentials and its compose file joins instead of
provisioning, its convergence then changes only what is the site's (an RODC's only what is local), and finish_join
deletes the join account. Proves: both join into their AD sites; the domain and the site's objects replicate both
ways; the site's agent works at its own DC with the id block the root gave; the join account is gone; an RODC's
convergence writes nothing and refuses writes; the password policy stays the root's.
    sudo python3 tests/samba/site_join.py
"""
import os
import subprocess
import sys
import time

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[0:0] = [os.path.join(REPO, "src"), os.path.dirname(os.path.abspath(__file__))]
from start_bind import start_bind  # noqa: E402
from start_dc import POLICY, dc_tls, run_dc, start_dc  # noqa: E402
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.directory.run_op import run_op  # noqa: E402
from fabriclib.federation.next_id_block import next_id_block  # noqa: E402
from fabriclib.samba.converge_domain import converge_domain  # noqa: E402
from fabriclib.samba.deploy_samba import deploy_samba  # noqa: E402
from fabriclib.samba.finish_join import finish_join  # noqa: E402
from fabriclib.samba.prepare_site import prepare_site  # noqa: E402
from fabriclib.secrets.random_password import random_password  # noqa: E402

W = os.path.join(os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests"), "samba-site-join")
NET, SUBNET = "sitejoin_net", "10.254.35.0/24"
ROOT, ROOT_IP, ROOT_BIND = "sjroot", "10.254.35.10", "sjroot-bind"
SITES = {"lab": ("sjlab", "10.254.35.20", "writable", "10.77.0.0/24"),
         "edge": ("sjedge", "10.254.35.30", "rodc", "10.78.0.0/24")}
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[-700:]}"))


def sh(cmd, ok=False, **kw):
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if ok and res.returncode:
        raise SystemExit(f"failed: {cmd[:6]}\n{res.stdout[-1500:]}{res.stderr[-1500:]}")
    return res


def search(container, expression, attrs, base=None):
    """An ldbsearch of a DC's own database: the output text."""
    args = ["docker", "exec", container, "ldbsearch", "-H", "/data/private/sam.ldb", expression, *attrs]
    if base:
        args[4:4] = ["-b", base]
    return sh(args).stdout


def until(pred, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(5)
    return False


def cleanup():
    sh(["docker", "rm", "-f", ROOT, ROOT_BIND, *[c for c, _, _, _ in SITES.values()]])
    sh(["docker", "network", "rm", NET])


cleanup()
root = start_dc(os.path.join(W, "root"), ROOT, NET, SUBNET, ROOT_IP)
RV, RS, ENV = root["v"], root["secrets"], root["env"]
start_bind(RV, ENV, ROOT, ROOT_BIND)
BASE = sh(["docker", "exec", ROOT, "ldbsearch", "-H", "/data/private/sam.ldb", "-s", "base", "-b", "", "defaultNamingContext"]
          ).stdout.split("defaultNamingContext: ")[1].split()[0]
check("the root's DC is up and BIND answers the AD zone", bool(BASE))

registry = {"sites": {}}
joined = {}
for site, (container, ip, dc_type, cidr) in SITES.items():
    # ---- at the root: what accept_join does before it answers
    block = next_id_block(RV, registry)
    accounts = {kind: random_password() for kind in ("agent", "keycloak", "radius")}
    join_pw = random_password()
    done = prepare_site(RV, site, [{"name": "lan", "cidr": cidr}], block, accounts, join_pw, container=ROOT)
    registry["sites"][site] = {"id_range": block, "dc": dc_type}
    expires = search(ROOT, f"(sAMAccountName=fabric-join-{site})", ["accountExpires", "memberOf"])
    check(f"{site}: the root prepares the site — its OU, groups, service accounts, id block, and a join account that "
          "expires", f"group {site}-admins created" in " ".join(done) and "Domain Admins" in expires
          and "accountExpires: 9223372036854775807" not in expires and "accountExpires:" in expires, done)
    # ---- at the site: what its setup does with the answer
    work = os.path.join(W, site)
    sh(["rm", "-rf", work])
    v = yaml.safe_load(ENV.get_template("vars.yaml.j2").render(
        domain=f"{site}.lan.j-j.family", hostname=f"dc-{site}", host_ip=ip, lan_cidr=cidr,
        lan_gateway=cidr.rsplit(".", 1)[0] + ".1", site_name=site, ad_domain=RV["ad_domain"],
        ad_password_policy=POLICY, deploy_base_dir=work, ad_ntp_signd_dir=os.path.join(work, "ntp_signd"),
        ad_dc_type=dc_type, ad_join_server=ROOT_IP, ad_join_server_name=RV["hostname_dc"], posix_id_range=block))
    secrets = {"ad_admin_password": random_password(), **{f"ad_{k}_password": p for k, p in accounts.items()},
               "ad_join": {"user": f"fabric-join-{site}", "password": join_pw}}
    os.makedirs(os.path.join(work, "stepca", "data", "certs"))
    sh(["cp", root["root_ca"], os.path.join(work, "stepca", "data", "certs", "root_ca.crt")], ok=True)
    deploy_samba(v, secrets, ENV)
    check(f"{site}: deploy writes the join credentials (0600) and points the DC at the root's DNS until it joined",
          oct(os.stat(os.path.join(work, "samba", "secrets", "join.auth")).st_mode & 0o777) == "0o600"
          and f"nameserver {ROOT_IP}" in open(os.path.join(work, "samba", "resolv.conf")).read())
    dc_tls(v, root["root_ca"], root["root_key"])
    try:
        run_dc(v, container, NET, ENV, tries=120)
        up = True
    except RuntimeError as e:
        up = False
        print(f"    {e}")
    logs = sh(["docker", "logs", container]).stdout
    check(f"{site}: its DC joins the domain as {'a read-only' if dc_type == 'rodc' else 'a writable'} DC "
          f"(not a domain of its own)", up and "joined" in logs and "provisioning" not in logs, logs[-800:])
    if not up:
        continue
    server = search(ROOT, f"(&(objectClass=server)(cn=dc-{site}))", ["distinguishedName"],
                    base=f"CN=Sites,CN=Configuration,{BASE}")
    check(f"{site}: the DC sits in its own AD site", f"CN=Servers,CN={site},CN=Sites" in server, server)
    fed = os.path.join(work, "federation.yaml")
    with open(fed, "w") as f:
        yaml.safe_dump({"sites": {}, "upstream": {"site_name": "lan"}}, f)
    try:
        changed = converge_domain(v, fed, secrets, container=container)
        again = converge_domain(v, fed, secrets, container=container)
        conv_err = ""
    except ValidationError as e:
        changed, again, conv_err = [], ["error"], str(e)
    check(f"{site}: the site's convergence runs at its DC, a second time changes nothing, and never touches the "
          f"domain's policy", not conv_err and again == [] and not any("password policy" in c for c in changed),
          conv_err or (changed, again))
    note = finish_join(v, secrets, container)
    check(f"{site}: the join account is deleted at the root once joined",
          "deleted" in note and until(lambda: "sAMAccountName" not in search(
              ROOT, f"(sAMAccountName=fabric-join-{site})", ["sAMAccountName"]), 60), note)
    joined[site] = (container, v, secrets)

# ---- a writable site: its own writes, both directions of replication, its id block
if "lab" in joined:
    container, v, secrets = joined["lab"]
    info = run_op(v, secrets, "site_info", container=container)
    check("lab: its agent signs in at its own DC and reads its site's id block (the root's second block)",
          info["id_range"] == registry["sites"]["lab"]["id_range"], info)
    made = run_op(v, secrets, "create_person", {"uid": "labby", "first": "Lab", "last": "By", "email": "labby@lab.test",
                                                "password": "Ot-" + random_password(20), "gid": 5000,
                                                "home_base": "/home", "shell": "/bin/bash"}, container)
    first, last = (int(x) for x in registry["sites"]["lab"]["id_range"].split("-"))
    check("lab: a person made at the site takes a uid from the site's own block", first <= made["uidNumber"] <= last,
          made)
    # AD's KCC builds the return path from the site link within its 5-minute round
    check("lab -> root: the person reaches the root's DC (AD replication over the site link)",
          until(lambda: "sAMAccountName: labby" in search(ROOT, "(sAMAccountName=labby)", ["sAMAccountName"]), 420))
    run_op(RV, RS, "create_person", {"uid": "rooty", "first": "Root", "last": "Y", "email": "rooty@lan.test",
                                     "password": "Ot-" + random_password(20), "gid": 5000, "home_base": "/home",
                                     "shell": "/bin/bash"}, ROOT)
    check("root -> lab: a person made at the root reaches the site's DC",
          until(lambda: "sAMAccountName: rooty" in search(container, "(sAMAccountName=rooty)", ["sAMAccountName"])))

# ---- a read-only site: the domain to read, nothing to write
if "edge" in joined:
    container, v, secrets = joined["edge"]
    check("edge: the domain replicated to the RODC (the site's OU and the root's people)",
          "OU=edge,OU=sites" in search(container, "(ou=edge)", ["dn"]))
    try:
        run_op(v, secrets, "create_person", {"uid": "edgy", "first": "E", "last": "D", "email": "e@edge.test",
                                             "password": "Ot-" + random_password(20), "gid": 5000,
                                             "home_base": "/home", "shell": "/bin/bash"}, container)
        wrote = True
    except ValidationError:
        wrote = False
    check("edge: writes at the RODC are refused (they belong to a writable DC)", not wrote)

# ---- the Federation tab's view of it (S8.5): AD's own replication state and conflict objects, at the root
from fabriclib.samba.list_conflicts import list_conflicts  # noqa: E402
from fabriclib.samba.replication_status import replication_status  # noqa: E402
def partners(container):
    rep = replication_status(container)
    return rep, {n["from"].split(",")[1].upper() for n in rep["neighbours"] if "," in n["from"] and not n["failures"]}


rep, got = partners(ROOT)
check("the root's replication status: the writable site's DC is an inbound neighbour, every partition succeeding "
      "(an RODC only pulls)", not rep["error"] and "CN=DC-LAB" in got and "CN=DC-EDGE" not in got
      and all(n["last_success"] for n in rep["neighbours"]), rep)
rep, got = partners(SITES["edge"][0])
check("the RODC's replication status: it pulls from the root", not rep["error"] and "CN=DC1" in got, rep)
check("no conflict objects in the domain", list_conflicts(ROOT) == [], list_conflicts(ROOT))

if not os.environ.get("FABRIC_TEST_KEEP"):
    cleanup()
print(f"\n{FAILED and 'FAILED' or 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
