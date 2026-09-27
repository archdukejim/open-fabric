"""Unit test for deploy.py zone handling with rndc stubbed out (run in WSL)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fabric", "lib"))
import deploy  # noqa: E402

calls = []
FREEZE_OK = {"lan.test"}          # dynamic zone: freeze/thaw succeed


class R:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def fake_rndc(args, timeout=15):
    calls.append(args)
    verb, zone = args.split()[0], args.split()[-1]
    if verb in ("freeze", "thaw"):
        return R(0 if zone in FREEZE_OK else 1)
    return R(0)


deploy.rndc = fake_rndc
uid, gid = os.getuid(), os.getgid()
ZONE = """$ORIGIN lan.test.
@ IN SOA ns.lan.test. hostmaster.lan.test. (
                        {serial} ; Serial (Epoch timestamp offset)
                        3600 )
{records}
"""
ok = True
with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
    def write(d, name, serial, records):
        with open(os.path.join(d, name), "w") as f:
            f.write(ZONE.format(serial=serial, records=records))

    # deployed: old records + a journal; rendered: same records, new serial
    write(dst, "db.lan.test", 100, "www A 1.1.1.1")
    open(os.path.join(dst, "db.lan.test.jnl"), "w").write("journal")
    write(src, "db.lan.test", 200, "www A 1.1.1.1")
    changed = deploy.deploy_zone_files(src, dst, uid, gid)
    print("unchanged records ignored despite new serial:", changed == [])
    ok &= changed == []

    # now a real change (the shelfmark case)
    write(src, "db.lan.test", 300, "www A 1.1.1.1\nshelfmark CNAME nas25-apps")
    write(src, "db.7.168.192.in-addr.arpa", 300, "53 PTR pi-core.lan.test.")
    changed = deploy.deploy_zone_files(src, dst, uid, gid)
    names = [z for z, _, _ in changed]
    print("changed zones detected:", names)
    ok &= sorted(names) == ["7.168.192.in-addr.arpa", "lan.test"]
    for zone, s, d in changed:
        deploy.reload_zone(zone, s, d, uid, gid)
    print("rndc calls:", calls)
    ok &= calls[:2] == ["freeze lan.test", "thaw lan.test"] or calls[2:4] == ["freeze lan.test", "thaw lan.test"]
    ok &= "reload 7.168.192.in-addr.arpa" in calls
    deployed = open(os.path.join(dst, "db.lan.test")).read()
    print("new record deployed:", "shelfmark" in deployed)
    ok &= "shelfmark" in deployed
    print("stale journal removed:", not os.path.exists(os.path.join(dst, "db.lan.test.jnl")))
    ok &= not os.path.exists(os.path.join(dst, "db.lan.test.jnl"))

print("ZONE TEST", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
