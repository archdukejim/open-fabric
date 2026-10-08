"""This DC's inbound replication, read from its own database (manual 1.9.8.5, 1.9.8.9): each partition's `repsFrom`
— the partner, the last success, the failures since — without an RPC sign-in, so a read-only DC can show it too.
    docker exec samba python3 /fabric/read_replication.py
Prints one JSON object: {"neighbours": [{"partition", "from", "last_success", "failures", "message"}]}."""
import datetime
import json
import sys

import ldb
from samba.dcerpc import drsblobs
from samba.ndr import ndr_unpack

from open_samdb import open_samdb

CONF = "/data/etc/smb.conf"


def _when(nttime):
    """Purpose: an NTTIME (100 ns since 1601) as text.
    Inputs:  nttime — int; 0 for never.
    Returns: str, "" for never.
    Fails:   never.
    Feeds:   read_replication."""
    if not nttime:
        return ""
    return datetime.datetime.fromtimestamp(nttime / 10_000_000 - 11644473600,
                                           datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def read_replication():
    """Purpose: every partition's inbound neighbours as this DC records them.
    Inputs:  none (the DC's own database, as the system).
    Returns: {"neighbours": [{"partition", "from" (the partner's NTDS Settings DN, or its GUID's DNS name),
             "last_success", "failures" (consecutive), "message" ("was successful" or the last WERROR code)}]}.
    Fails:   ldb.LdbError from a search.
    Feeds:   this script's main."""
    samdb, _ = open_samdb(CONF)
    root = samdb.search(base="", scope=ldb.SCOPE_BASE, attrs=["namingContexts", "configurationNamingContext"])[0]
    config = str(root["configurationNamingContext"][0])
    out = []
    for nc in sorted(str(x) for x in root["namingContexts"]):
        res = samdb.search(base=nc, scope=ldb.SCOPE_BASE, attrs=["repsFrom"])
        for raw in res[0].get("repsFrom", []):
            ctr = ndr_unpack(drsblobs.repsFromToBlob, bytes(raw)).ctr
            guid = str(ctr.source_dsa_obj_guid)
            result = ctr.result_last_attempt          # a WERROR: (code, text) from the bindings, or a bare code
            code, text = result if isinstance(result, tuple) else (result, f"WERROR 0x{int(result) & 0xffffffff:08x}")
            found = samdb.search(base=config, scope=ldb.SCOPE_SUBTREE, expression=f"(objectGUID={guid})", attrs=["dn"])
            out.append({"partition": nc, "from": str(found[0].dn) if found else ctr.other_info.dns_name,
                        "last_success": _when(ctr.last_success), "failures": int(ctr.consecutive_sync_failures),
                        "message": "was successful" if not code else str(text)})
    return {"neighbours": out}


if __name__ == "__main__":
    try:
        print(json.dumps(read_replication()))
    except Exception as e:                  # reported by the caller; the DC keeps running
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
