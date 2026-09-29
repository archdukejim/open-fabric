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


DST = {}                          # set below: the deployed zone folder
RACE = {"lan.test": True}         # BIND's own write lands after ours, once


def fake_rndc(args, timeout=15):
    """rndc as BIND answers it. zonestatus reports the serial of the zone
    file BIND loaded; the first thaw of lan.test puts the old file back, as
    BIND's freeze-time write did in the sandbox (the race reload_zone must
    detect and repeat)."""
    calls.append(args)
    verb, zone = args.split()[0], args.split()[-1]
    path = os.path.join(DST.get("dir", ""), f"db.{zone}")
    if verb == "thaw" and RACE.pop(zone, False):
        with open(path, "w") as f:
            f.write(DST["old"])
    if verb in ("freeze", "thaw"):
        return R(0 if zone in FREEZE_OK else 1)
    if verb == "zonestatus":
        serial = deploy._file_serial(path) if os.path.exists(path) else None
        return R(0, f"name: {zone}\nserial: {serial}\n")
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
    DST.update(dir=dst, old=open(os.path.join(dst, "db.lan.test")).read())
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
    swaps = [c for c in calls if c in ("freeze lan.test", "thaw lan.test")]
    print("BIND's late write detected and the swap repeated:", swaps == ["freeze lan.test", "thaw lan.test"] * 2)
    ok &= swaps == ["freeze lan.test", "thaw lan.test"] * 2
    ok &= "reload 7.168.192.in-addr.arpa" in calls
    deployed = open(os.path.join(dst, "db.lan.test")).read()
    print("new record deployed:", "shelfmark" in deployed)
    ok &= "shelfmark" in deployed
    print("stale journal removed:", not os.path.exists(os.path.join(dst, "db.lan.test.jnl")))
    ok &= not os.path.exists(os.path.join(dst, "db.lan.test.jnl"))

print("ZONE TEST", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
