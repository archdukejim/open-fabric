from fabriclib.dns_filter.show_filter_status import show_filter_status
from fabriclib.dns_filter.update_lists import update_lists

USAGE = """usage: fabricctl dns-filter lists [--scheduled]  fetch every list now, reload the ones that changed
       fabricctl dns-filter status              the resolver, and each list's state"""


def run_dns_filter_command(v, argv):
    """Purpose: `fabricctl dns-filter lists | status` (manual 1.12.2.10): the BIND resolver's lists (routing only).
    Inputs:  v — rendered vars of the install; argv — list of str after "dns-filter" (default status). `lists
             --scheduled` is the daily timer's run (fabric-dns-lists).
    Returns: exit status: 0 success; 1 a list failed or the resolver is not answering; 2 usage, or the resolver is
             off (dns_filter is not bind).
    Fails:   OSError from update_lists writing the lists folder.
    Feeds:   fabriclib/cli.py (`fabricctl dns-filter`)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    if cmd == "status" and not args:
        return show_filter_status(v)
    if cmd == "lists" and args in ([], ["--scheduled"]):
        if not v.get("install_resolver"):
            print(f"the BIND resolver is off (dns_filter: {v.get('dns_filter')}): nothing to fetch")
            return 2
        result = update_lists(v)
        for zone, st in result["lists"].items():
            mark = "FAILED" if st.get("error") and st["name"] in result["failed"] else (
                "changed" if zone in result["changed"] else "unchanged")
            print(f"  {st['name']}: {mark}" + (f" — {st['error']}" if mark == "FAILED" else
                                               f", {st.get('rules', 0)} rules, {st.get('skipped', 0)} skipped"))
        return 1 if result["failed"] else 0
    print(USAGE)
    return 2
