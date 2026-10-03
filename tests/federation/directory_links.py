"""The replication plan (fabriclib/federation/directory_links.py, design federation.md §3.2a) for the shapes a site
can take: standalone, the root with a site, a leaf site, a site with sites below it (a hub), a link without its
secret. No containers: the plan is data."""
import os
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                "fabricctl", "lib"))
from fabriclib.federation.directory_links import directory_links  # noqa: E402

BASE = "dc=lan"
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))


def plan(me, registry, secrets):
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(registry, f)
    try:
        return directory_links({"site_name": me, "ldap_base_dn": BASE, "ldap_local_dn": f"ou={me},{BASE}"},
                               {"federation_replication": secrets}, f.name)
    finally:
        os.unlink(f.name)


def roles(p):
    return {r["suffix"]: r["role"] for r in p["replicas"]}


alone = plan("lan", {}, {})
check("standalone: nothing replicates (no changelog)", alone == {"replicas": [], "agreements": [], "backends": []},
      alone)

root = plan("lan", {"sites": {"lab": {"ldap_host": "ldap.lab.lan", "ldap_port": 636}}}, {"lab": "S1"})
check("root: supplies the organisation and keeps a copy of lab's part",
      roles(root) == {BASE: "supplier", "ou=lan,dc=lan": "supplier", "ou=lab,dc=lan": "consumer"}, roles(root))
check("root: the organisation goes to lab, bound as repl-from-lan with the link's secret",
      [(a["suffix"], a["name"], a["host"], a["bind_dn"], a["secret"]) for a in root["agreements"]]
      == [(BASE, "to-lab", "ldap.lab.lan", "cn=repl-from-lan,cn=config", "S1")], root["agreements"])
copy = next(r for r in root["replicas"] if r["suffix"] == "ou=lab,dc=lan")
check("root: lab may push its part (account repl-from-lab), writes there are referred to lab",
      copy["accounts"] == {"repl-from-lab": "S1"} and copy["referral"] == "ldaps://ldap.lab.lan:636"
      and root["backends"] == [{"suffix": "ou=lab,dc=lan", "name": "part_lab"}], copy)

up = {"site_name": "lan", "ldap_host": "ldap.lan", "ldap_port": 636}
leaf = plan("lab", {"upstream": up}, {"upstream": "S1"})
check("site: a read-only copy of the organisation (consumer) referring writes to the root, its part supplied here",
      roles(leaf) == {BASE: "consumer", "ou=lab,dc=lan": "supplier"}
      and leaf["replicas"][0]["referral"] == "ldaps://ldap.lan:636"
      and leaf["replicas"][0]["accounts"] == {"repl-from-lan": "S1"}, leaf["replicas"])
check("site: its part goes to the parent, bound as repl-from-lab",
      [(a["suffix"], a["host"], a["bind_dn"]) for a in leaf["agreements"]]
      == [("ou=lab,dc=lan", "ldap.lan", "cn=repl-from-lab,cn=config")], leaf["agreements"])

hub = plan("lab", {"upstream": up, "sites": {"lab2": {"ldap_host": "ldap.lab2.lan"}}}, {"upstream": "S1", "lab2": "S2"})
check("a site with a site below it is a hub of the organisation and passes it on",
      roles(hub)[BASE] == "hub" and any(a["name"] == "to-lab2" and a["secret"] == "S2" for a in hub["agreements"]),
      hub)

missing = plan("lan", {"sites": {"old": {"ldap_host": "ldap.old.lan"}}}, {})
check("a site that joined before M5 (no directory secret) is left out until it joins again",
      not any("old" in a["name"] for a in missing["agreements"]) and not missing["backends"], missing)
sys.exit(1 if FAILED else 0)
