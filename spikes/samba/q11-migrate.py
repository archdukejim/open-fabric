"""S0 spike Q11, step 2: turn fabric's 389-DS export (export.json) into AD entries (LDIF for ldbadd/ldbmodify on the
DC) — people, groups, device roles, devices and networks — and say what is not carried over and why.
    python3 q11-migrate.py <export.json> <389-DS base> <AD base> <site> <out dir>
Writes <out>/add.ldif (new entries), <out>/modify.ldif (changes to entries AD already has), <out>/plan.json."""
import json
import os
import sys

src, OLD, NEW, SITE, OUT = sys.argv[1:6]
entries = json.load(open(src))
SITE_OU = f"OU={SITE},OU=sites,{NEW}"
OLD_LOCAL = f"ou={SITE},{OLD}".lower()
# fabric's groups whose name AD already has (sAMAccountName is unique across the domain): fabric's "users" (everyone)
# is AD's Domain Users; the existing group gets fabric's gidNumber instead of a new one
EXISTING = {"users": "CN=Domain Users,CN=Users," + NEW}
plan = {"people": [], "groups": [], "roles": [], "devices": [], "networks": [], "skipped": []}
add, mod, dn_map = [], [], {}


def one(a, k):
    return (a.get(k) or [None])[0]


def kind(dn, a):
    oc = {o.lower() for o in a.get("objectClass", [])}
    low = dn.lower()
    if "inetorgperson" in oc and ",ou=users,ou=accounts," in low:
        return "person"
    if "fabricrole" in oc:
        return "role"
    if "groupofnames" in oc and ",ou=groups," in low:
        return "group"
    if "fabricdevice" in oc:
        return "device"
    if "fabricnetwork" in oc:
        return "network"
    return None


def block(dn, attrs):
    lines = [f"dn: {dn}"]
    for k, vs in attrs:
        lines += [f"{k}: {v}" for v in (vs if isinstance(vs, list) else [vs]) if v not in (None, "")]
    return "\n".join(lines) + "\n"


# people first: every other entry's DNs (members, owners) are mapped through them
for dn, a in entries:
    if kind(dn, a) == "person":
        uid = one(a, "uid")
        new = f"CN={uid},OU=people,{NEW}"
        dn_map[dn.lower()] = new
        plan["people"].append(uid)
        add.append(block(new, [("objectClass", "user"), ("sAMAccountName", uid), ("userPrincipalName",
                     f"{uid}@{NEW.replace('DC=', '').replace(',', '.').lower()}"), ("givenName", one(a, "givenName")),
                     ("sn", one(a, "sn")), ("displayName", one(a, "cn")), ("mail", one(a, "mail")),
                     ("uidNumber", one(a, "uidNumber")), ("gidNumber", one(a, "gidNumber")),
                     ("unixHomeDirectory", one(a, "homeDirectory")), ("loginShell", one(a, "loginShell")),
                     # no password moves (389-DS keeps one-way hashes): disabled until the person sets one
                     ("userAccountControl", "514")]))
for dn, a in entries:
    k = kind(dn, a)
    cn = one(a, "cn")
    members = [dn_map[m.lower()] for m in a.get("member", []) if m.lower() in dn_map]
    dropped = [m for m in a.get("member", []) if m.lower() not in dn_map]
    if k == "group":
        plan["groups"].append(cn)
        if dropped:
            plan["skipped"].append({"what": f"members of group {cn}", "dns": dropped,
                                    "why": "service accounts of 389-DS: AD has its own (delegated rights)"})
        if cn.lower() in EXISTING:
            mod.append(block(EXISTING[cn.lower()], [("changetype", "modify"), ("replace", "gidNumber"),
                                                   ("gidNumber", one(a, "gidNumber"))]) + "-\n")
            continue
        add.append(block(f"CN={cn},OU=groups,{NEW}", [("objectClass", "group"), ("sAMAccountName", cn),
                         ("description", one(a, "description")), ("gidNumber", one(a, "gidNumber")),
                         ("member", members)]))
    elif k == "role":
        plan["roles"].append(cn)
        add.append(block(f"CN={cn},OU=device-roles,{NEW}", [("objectClass", ["group", "fabricRole"]),
                         ("sAMAccountName", f"role-{cn}"), ("description", one(a, "description")),
                         ("fabricPermission", a.get("fabricPermission", [])), ("fabricVlan", one(a, "fabricVlan")),
                         ("fabricPriority", one(a, "fabricPriority"))]))
    elif k == "device":
        plan["devices"].append(cn)
        owner = dn_map.get((one(a, "owner") or "").lower())
        add.append(block(f"CN={cn},OU=devices,{SITE_OU}", [
            ("objectClass", ["device", "ieee802Device", "fabricDevice", "fabricDeviceRoles"]),
            ("macAddress", a.get("macAddress", [])), ("fabricDeviceType", one(a, "fabricDeviceType")),
            ("fabricEnabled", one(a, "fabricEnabled")), ("fabricCertFingerprint", a.get("fabricCertFingerprint", [])),
            ("fabricRoleName", a.get("fabricRoleName", [])), ("description", one(a, "description")),
            ("owner", owner), ("serialNumber", one(a, "serialNumber"))]))
    elif k == "network":
        plan["networks"].append(cn)
        where = f"OU=networks,{SITE_OU}" if dn.lower().endswith(OLD_LOCAL) else f"OU=address-plan,{NEW}"
        add.append(block(f"CN={cn},{where}", [("objectClass", "fabricNetwork"), ("fabricCidr", one(a, "fabricCidr")),
                         ("fabricSite", one(a, "fabricSite")), ("fabricVlan", one(a, "fabricVlan")),
                         ("fabricNetworkKind", one(a, "fabricNetworkKind")),
                         ("fabricAllowOverlap", one(a, "fabricAllowOverlap")), ("description", one(a, "description"))]))
    elif k is None and "inetorgperson" in {o.lower() for o in a.get("objectClass", [])}:
        plan["skipped"].append({"what": dn, "why": "a 389-DS service account: replaced by AD's own accounts"})
ous = [f"OU=people,{NEW}", f"OU=groups,{NEW}", f"OU=device-roles,{NEW}", f"OU=address-plan,{NEW}",
       f"OU=devices,{SITE_OU}", f"OU=networks,{SITE_OU}"]
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/ous.ldif", "w") as f:
    f.write("\n".join(block(o, [("objectClass", "organizationalUnit")]) for o in ous))
with open(f"{OUT}/add.ldif", "w") as f:
    f.write("\n".join(add))
with open(f"{OUT}/modify.ldif", "w") as f:
    f.write("\n".join(mod))
with open(f"{OUT}/plan.json", "w") as f:
    json.dump(plan, f, indent=1)
print(json.dumps({k: (len(v) if k != "skipped" else [s["what"] for s in v]) for k, v in plan.items()}))
