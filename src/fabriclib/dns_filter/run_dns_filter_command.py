from fabriclib.common.errors import ValidationError
from fabriclib.dns_filter.dns_filter_stats import dns_filter_stats
from fabriclib.dns_filter.ingest_dns_log import ingest_dns_log
from fabriclib.dns_filter.read_query_log import read_query_log
from fabriclib.dns_filter.show_filter_status import show_filter_status
from fabriclib.dns_filter.update_lists import update_lists

USAGE = """usage: fabricctl dns-filter lists [--scheduled]  fetch every list now, reload the ones that changed
       fabricctl dns-filter status              the resolver, and each list's state
       fabricctl dns-filter log [--client ADDRESS] [--name NAME] [--blocked] [--limit N]
                                                the query log, newest first (a name: it and every name below it)
       fabricctl dns-filter stats               the last 24 hours, the last 7 days, per list, the most blocked names
       fabricctl dns-filter ingest [--scheduled]
                                                read the resolver's new log lines into the query log now"""


def _options(args):
    """Purpose: the options of `fabricctl dns-filter log`.
    Inputs:  args — list of str after "log".
    Returns: {"client", "name", "blocked_only", "limit"} for read_query_log.
    Fails:   ValidationError for an unknown option or one without its value.
    Feeds:   run_dns_filter_command."""
    out = {"client": "", "name": "", "blocked_only": False, "limit": 50}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--blocked":
            out["blocked_only"] = True
            i += 1
        elif a in ("--client", "--name", "--limit") and i + 1 < len(args):
            out[a[2:]] = args[i + 1]
            i += 2
        else:
            raise ValidationError(f"unknown option or missing value: {a}")
    return out


def _print_stats(s):
    """Purpose: the statistics as text.
    Inputs:  s — dns_filter_stats' result.
    Returns: None (prints).
    Fails:   never.
    Feeds:   run_dns_filter_command."""
    week = s["week"]
    share = round(100 * week["blocked"] / week["queries"], 1) if week["queries"] else 0
    print(f"last 7 days: {week['queries']} queries, {week['blocked']} blocked ({share}%)")
    print("last 24 hours (UTC):")
    for h in s["hours"]:
        print(f"  {h['hour'][11:16]}  {h['queries']:>7} queries  {h['blocked']:>6} blocked")
    print("by list and rules (7 days):")
    for z in s["zones"]:
        print(f"  {z['list'] or z['zone']}: {z['blocked']} blocked, {z['queries']} rewritten or passed")
    print("most blocked (7 days):")
    for t in s["top_blocked"]:
        print(f"  {t['count']:>6}  {t['name']}  ({t['list'] or t['zone']})")


def run_dns_filter_command(v, argv):
    """Purpose: `fabricctl dns-filter lists | status | log | stats | ingest` (manual 1.12.2.10, 1.12.2.13): the BIND
             resolver's lists and its query log (routing only).
    Inputs:  v — rendered vars of the install; argv — list of str after "dns-filter" (default status). `lists
             --scheduled` is the daily lists timer's run (fabric-dns-lists); `ingest --scheduled` the query log's
             (fabric-dns-log).
    Returns: exit status: 0 success; 1 a list failed, the resolver is not answering, or the query log refused (its
             reason printed); 2 usage, or the resolver or the query log is off.
    Fails:   OSError from update_lists or ingest_dns_log writing their files.
    Feeds:   fabriclib/cli.py (`fabricctl dns-filter`)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    try:
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
        if cmd == "ingest" and args in ([], ["--scheduled"]):
            r = ingest_dns_log(v)
            if "off" in r:
                print(f"the query log is off: {r['off']}")
                return 2
            print(f"query log: {r['queries']} queries and {r['rewrites']} rewrites read"
                  + (f", {r['skipped']} other lines" if r["skipped"] else ""))
            return 0
        if cmd == "log":
            r = read_query_log(v, **_options(args))
            if "off" in r:
                print(f"the query log is off: {r['off']}")
                return 2
            for e in r["entries"]:
                why = f"  {e['action']} via {e['list'] or e['zone']}" if e.get("action") else ""
                print(f"{e['at']}  {e['client']:<15} {e['view']:<10} {e['qtype']:<6} {e['name']}{why}")
            return 0
        if cmd == "stats" and not args:
            s = dns_filter_stats(v)
            if "off" in s:
                print(f"the query log is off: {s['off']}")
                return 2
            _print_stats(s)
            return 0
    except ValidationError as e:
        print(f"refused: {e}")
        return 1
    print(USAGE)
    return 2
