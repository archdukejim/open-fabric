import json
import os
import subprocess

from fabriclib.federation.configure_agreement import configure_agreement
from fabriclib.federation.configure_replica import configure_replica
from fabriclib.federation.directory_links import directory_links

# Runs inside the dirsrv container as Directory Manager: the agreements fabric made (named to-<site>) that the plan
# no longer has are removed (a removed site's copy of its part is kept: see configure_directory_links).
_PRUNE = r'''
import json, os, time, ldap
e = os.environ
keep = set(json.loads(e["F_KEEP"]))
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
gone = []
for dn, a in c.search_s("cn=mapping tree,cn=config", ldap.SCOPE_SUBTREE, "(objectClass=nsds5replicationagreement)",
                        ["cn", "nsDS5ReplicaRoot"]):
    name = a["cn"][0].decode()
    if name.startswith("to-") and f"{a['nsDS5ReplicaRoot'][0].decode()}|{name}" not in keep:
        c.delete_s(dn)
        gone.append(f"agreement {name}")
print(json.dumps(gone))
'''


def configure_directory_links(v, secrets, registry_path, container="dirsrv"):
    """Purpose: make this site's 389-DS replicate as the federation says (design federation.md §3.2a): copies of the
             parts of the sites that joined here, the replicas, the agreements; and remove what is no longer linked.
    Inputs:  v — fabric vars (directory_links); secrets — fabric's secrets (federation_replication);
             registry_path — config/federation.yaml; container — the dirsrv container.
    Returns: list of what changed ([] when everything already was so).
    Fails:   ValidationError / RuntimeError from configure_replica and configure_agreement (the first failing link
             stops the run: the next apply retries); RuntimeError when a backend cannot be created.
    Feeds:   setup/start_services (after seeding) and deploy/restart_changed (every apply: a site joined or was
             removed); tests/federation/replication.sh.
    Notes:   a removed site's copy (backend part_<site>) is kept until removed by hand
             (`dsconf localhost backend delete`): deleting directory data is never automatic."""
    plan = directory_links(v, secrets, registry_path)
    done = []
    listed = subprocess.run(["docker", "exec", container, "dsconf", "localhost", "backend", "suffix", "list"],
                            capture_output=True, text=True, timeout=60).stdout.lower()
    for b in plan["backends"]:
        if f"{b['suffix'].lower()} (" not in listed:
            res = subprocess.run(["docker", "exec", container, "dsconf", "localhost", "backend", "create", "--suffix",
                                  b["suffix"], "--be-name", b["name"], "--parent-suffix", v["ldap_base_dn"]],
                                 capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"creating the copy {b['suffix']} failed: {(res.stderr or res.stdout).strip()}")
            done.append(f"copy {b['suffix']}")
    for r in plan["replicas"]:
        done += configure_replica(r["suffix"], r["role"], r["replica_id"], r["accounts"], referral=r["referral"],
                                  container=container)
    for a in plan["agreements"]:
        state = configure_agreement(a["suffix"], a["name"], a["host"], a["port"], a["bind_dn"], a["secret"],
                                    a["description"], container=container)
        if state != "current":
            done.append(f"agreement {a['name']} {state}")
    keep = json.dumps([f"{a['suffix']}|{a['name']}" for a in plan["agreements"]])
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_KEEP", container, "python3", "-"],
                         input=_PRUNE, env={**os.environ, "F_KEEP": keep},
                         capture_output=True, text=True, timeout=60)
    if res.returncode == 0 and res.stdout.strip():
        done += json.loads(res.stdout.strip().splitlines()[-1])
    return done
