import json
import os
import subprocess

from fabriclib.common.errors import ValidationError

# Runs inside the dirsrv container as Directory Manager over LDAPI; the link secret arrives in the environment.
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
replica = f"cn=replica,cn={ldap.dn.escape_dn_chars(IN['suffix'])},cn=mapping tree,cn=config"
dn = f"cn={IN['name']},{replica}"
want = {"nsDS5ReplicaRoot": [IN["suffix"].encode()], "nsDS5ReplicaHost": [IN["host"].encode()],
        "nsDS5ReplicaPort": [str(IN["port"]).encode()], "nsDS5ReplicaTransportInfo": [b"LDAPS"],
        "nsDS5ReplicaBindMethod": [b"SIMPLE"], "nsDS5ReplicaBindDN": [IN["bind_dn"].encode()],
        "nsDS5ReplicaCredentials": [e["F_SECRET"].encode()], "description": [IN["description"].encode()]}
try:
    have = c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", ["*", "nsds5replicaLastInitStatus",
                                                               "nsds5BeginReplicaRefresh"])[0][1]
except ldap.NO_SUCH_OBJECT:
    have = None
if have is None:
    c.add_s(dn, ldap.modlist.addModlist({"objectClass": [b"top", b"nsds5replicationagreement"],
                                         "cn": [IN["name"].encode()], **want}))
    # first time: a total update sends the whole suffix; afterwards only changes
    c.modify_s(dn, [(ldap.MOD_REPLACE, "nsds5BeginReplicaRefresh", [b"start"])])
    state = "created"
else:
    mods = [(ldap.MOD_REPLACE, k, v) for k, v in want.items() if k != "nsDS5ReplicaCredentials"
            and sorted(have.get(k, [])) != sorted(v)]
    mods.append((ldap.MOD_REPLACE, "nsDS5ReplicaCredentials", want["nsDS5ReplicaCredentials"]))
    c.modify_s(dn, mods)
    state = "updated" if len(mods) > 1 else "current"
    # a first copy that never completed (the other site was not up yet when the link was made) is started again:
    # 389-DS retries changes by itself, but not the initial total update
    # (389-DS reports success as "Error (0) Total update succeeded"; nsds5BeginReplicaRefresh is set while one runs)
    init = (have.get("nsds5replicaLastInitStatus") or [b""])[0].decode().lower()
    running = bool(have.get("nsds5BeginReplicaRefresh"))
    if not IN.get("reinit") and not running and "succeeded" not in init and "in progress" not in init:
        c.modify_s(dn, [(ldap.MOD_REPLACE, "nsds5BeginReplicaRefresh", [b"start"])])
        state += "+init"
    if IN.get("reinit"):
        c.modify_s(dn, [(ldap.MOD_REPLACE, "nsds5BeginReplicaRefresh", [b"start"])])
        state += "+reinit"
print(json.dumps(state))
'''


def configure_agreement(suffix, name, host, port, bind_dn, secret, description="", reinit=False, container="dirsrv"):
    """Purpose: a replication agreement from this 389-DS (supplier or hub of `suffix`) to another site's copy, over
             LDAPS verified against the organisation's root CA (manual 1.8.3.2).
    Inputs:  suffix — the replicated suffix; name — the agreement's name (to-<site>); host — the other site's LDAP
             name (its certificate's name, resolvable here through the federation's DNS links); port — its LDAPS
             port (636); bind_dn — the link account at the other site (cn=repl-from-<this site>,cn=config); secret
             — the link's secret (environment only); description — shown in status; reinit — send the whole suffix
             again; container — the dirsrv container.
    Returns: "created" (with a first total update started), "updated", "current"; with "+init" when the first copy
             had not completed (started again) and "+reinit" when asked.
    Fails:   ValidationError when 389-DS is not running; RuntimeError for other failures (the container's message).
    Feeds:   federation/configure_directory_links (apply); tests/federation/replication.sh."""
    env = {**os.environ, "F_SECRET": secret,
           "F_JSON": json.dumps({"suffix": suffix, "name": name, "host": host, "port": int(port), "bind_dn": bind_dn,
                                 "description": description, "reinit": bool(reinit)})}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_JSON", "-e", "F_SECRET", container, "python3", "-"],
                         input=_IN_CONTAINER, env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0 and ("No such container" in res.stderr or "is not running" in res.stderr):
        raise ValidationError("389-DS (dirsrv) is not running — `sudo fabricctl status`")
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"replication agreement failed: {(res.stderr or res.stdout).strip()[-500:]}")
    return json.loads(res.stdout.strip().splitlines()[-1])
