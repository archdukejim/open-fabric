import sys

from fabriclib.vault.vault_status import vault_status


def run_vault_command(v, argv):
    """`fabricctl vault status`: OpenBao at a glance (never prints secrets).
    Exit 0 when unsealed, 1 otherwise."""
    if argv[:1] not in ([], ["status"]):
        print("usage: fabricctl vault status", file=sys.stderr)
        return 2
    s = vault_status(v)
    if not s["reachable"]:
        print(f"OpenBao: unreachable — {s.get('error', '')}")
        return 1
    state = "not initialised" if not s["initialized"] else ("SEALED" if s["sealed"] else "unsealed")
    print(f"OpenBao {s['version']}: {state}  ({s['seal_type']} seal, {s['storage']} storage)  {s['url']}")
    print(f"seal key: {s['key']['path']} — {s['key']['detail']}")
    for m in s.get("mounts", []):
        print(f"  {m['path']:<12} {m['type']}{' v' + m['version'] if m['version'] else ''}  {m['description']}")
    if s.get("secrets"):
        print(f"fabric's secrets: in OpenBao (fabric/secrets, version {s['secrets']['version']}, "
              f"updated {s['secrets']['updated']})")
    if s.get("auth"):
        print(f"  auth: {', '.join(s['auth'])}")
    if s.get("error"):
        print(f"note: {s['error']}")
    return 0 if s["initialized"] and not s["sealed"] else 1
