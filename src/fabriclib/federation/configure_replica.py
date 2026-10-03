import json
import os
import subprocess

from fabriclib.common.errors import ValidationError

ROLES = {"supplier": ("3", "1"), "hub": ("2", "1"), "consumer": ("2", "0")}   # nsDS5ReplicaType, nsDS5Flags
READ_ONLY_ID = "65535"                                                       # every hub and consumer

# Runs inside the dirsrv container as Directory Manager over LDAPI; secrets arrive in the environment.
_IN_CONTAINER = r'''
import json, os, time, ldap, ldap.modlist
e = os.environ
IN = json.loads(e["F_JSON"])
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
def get(dn, attrs=None):
    try:
        return c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", attrs)[0][1]
    except ldap.NO_SUCH_OBJECT:
        return None
done = []
# one bind account per link that may push to this server (cn=<name>,cn=config), with the link's secret
for name, secret in json.loads(e["F_ACCOUNTS"]).items():
    dn = f"cn={name},cn=config"
    if get(dn) is None:
        c.add_s(dn, ldap.modlist.addModlist({"objectClass": [b"top", b"person"], "cn": [name.encode()],
                                             "sn": [b"replication"], "userPassword": [secret.encode()]}))
        done.append(f"account {name}")
    else:
        c.modify_s(dn, [(ldap.MOD_REPLACE, "userPassword", [secret.encode()])])
suffix = IN["suffix"]
replica = f"cn=replica,cn={ldap.dn.escape_dn_chars(suffix)},cn=mapping tree,cn=config"
binders = [f"cn={n},cn=config".encode() for n in json.loads(e["F_ACCOUNTS"])]
want = {"nsDS5ReplicaRoot": [suffix.encode()], "nsDS5ReplicaType": [IN["type"].encode()],
        "nsDS5Flags": [IN["flags"].encode()], "nsDS5ReplicaId": [IN["id"].encode()]}
if IN.get("referral"):                     # a read-only copy refers writes to where the suffix is written
    want["nsDS5ReplicaReferral"] = [IN["referral"].encode()]
have = get(replica)
if have is None:
    c.add_s(replica, ldap.modlist.addModlist({"objectClass": [b"top", b"nsds5replica", b"extensibleObject"],
                                              "cn": [b"replica"], **want,
                                              **({"nsDS5ReplicaBindDN": binders} if binders else {})}))
    done.append(f"replica {IN['role']}")
else:
    mods = [(ldap.MOD_REPLACE, k, v) for k, v in want.items() if sorted(have.get(k, [])) != sorted(v)]
    if binders and sorted(x.lower() for x in have.get("nsDS5ReplicaBindDN", [])) != sorted(x.lower() for x in binders):
        mods.append((ldap.MOD_REPLACE, "nsDS5ReplicaBindDN", binders))
    if mods:
        c.modify_s(replica, mods)
        done.append(f"replica {IN['role']} updated")
print(json.dumps(done))
'''


def configure_replica(suffix, role, replica_id, accounts, referral=None, container="dirsrv"):
    """Purpose: make this 389-DS a replica of one suffix (manual 1.8.3.2): the supplier where it is
             written, a hub that passes it on, or a read-only consumer; and the link accounts allowed to push to it.
    Inputs:  suffix — the replicated suffix (the organisation's base DN, or a site's part ou=<site>,<base>); role —
             "supplier", "hub" or "consumer"; replica_id — 1..65534 for a supplier (ignored otherwise: hubs and
             consumers share 65535); accounts — {account name: secret}: one per link whose supplier pushes here
             (cn=<name>,cn=config, password = the link's secret); referral — for a hub or consumer, the LDAP URL
             of the site where the suffix is written (ldaps://ldap.<root domain>:636): a write here is referred
             there; container — the dirsrv container.
    Returns: list of what changed ([] when it already was so).
    Fails:   ValidationError for an unknown role, a bad replica id or when 389-DS is not running; RuntimeError for
             other failures (the container's message).
    Feeds:   federation/configure_directory_links (apply); tests/federation/replication.sh.
    Notes:   secrets travel in the environment of `docker exec` (never argv). The changelog is the backend's own
             (389-DS ≥ 1.4.3): suppliers and hubs log changes (nsDS5Flags 1)."""
    if role not in ROLES:
        raise ValidationError(f"replica role must be supplier, hub or consumer (got {role!r})")
    rid = str(int(replica_id)) if role == "supplier" else READ_ONLY_ID
    if role == "supplier" and not 0 < int(rid) < 65535:
        raise ValidationError("a supplier's replica id is 1 to 65534")
    rtype, flags = ROLES[role]
    env = {**os.environ, "F_JSON": json.dumps({"suffix": suffix, "role": role, "type": rtype, "flags": flags,
                                                "id": rid, "referral": referral if role != "supplier" else None}),
           "F_ACCOUNTS": json.dumps(accounts)}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_JSON", "-e", "F_ACCOUNTS", container, "python3", "-"],
                         input=_IN_CONTAINER, env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0 and ("No such container" in res.stderr or "is not running" in res.stderr):
        raise ValidationError("389-DS (dirsrv) is not running — `sudo fabricctl status`")
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"replica setup failed: {(res.stderr or res.stdout).strip()[-500:]}")
    return json.loads(res.stdout.strip().splitlines()[-1])
