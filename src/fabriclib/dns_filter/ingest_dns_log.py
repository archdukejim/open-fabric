import datetime
import fcntl
import json
import os
import re

from fabriclib.common.write_file_if_changed import write_file_if_changed
from fabriclib.dns_filter.common.dnslog_psql import dnslog_psql
from fabriclib.dns_filter.common.resolver_paths import resolver_paths
from fabriclib.dns_filter.ensure_dnslog_db import ensure_dnslog_db

CLIENT = r"client @\S+ ([0-9a-fA-F:.]+)#(\d+) \((\S+)\): view (\S+):"
QUERY = re.compile(r"^(\S+ \S+) " + CLIENT + r" query: (\S+) IN (\S+) ")
RPZ = re.compile(r"^(\S+ \S+) " + CLIENT + r" rpz \S+ (\S+) rewrite (\S+)/(\S+)/IN via (\S+)")
ZONE = re.compile(r"((?:[0-9a-f]{12}\.list|[a-z0-9-]+)\.rpz)$")
MAX_BATCH = 64 * 1024 * 1024           # read at most this much per file and run (the rest the next run)

PURGE = """
DELETE FROM queries WHERE at < now() - interval '7 days';
DELETE FROM stats_hourly WHERE hour < now() - interval '90 days';
DELETE FROM stats_blocked WHERE day < (now() AT TIME ZONE 'UTC')::date - 90;
"""


def _new_lines(folder, name, seen):
    """Purpose: the complete lines added to a resolver log since the last run, a rotated file finished first.
    Inputs:  folder — the log folder; name — "query.log" or "rpz.log"; seen — {"inode", "offset"} from the last run,
             or None.
    Returns: (lines: list of str, place: {"inode", "offset"} after them, or None when the file is not there).
    Fails:   OSError reading the files.
    Feeds:   ingest_dns_log.
    Notes:   BIND renames a full log to <name>.0 (versions 2): a file with the last run's inode there is read on from
             the last offset first. A file shorter than the offset was truncated: read from its start."""
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        return [], None
    cur = os.stat(path)
    data = b""
    offset = 0
    if seen:
        rotated = path + ".0"
        if seen["inode"] == cur.st_ino:
            offset = seen["offset"] if seen["offset"] <= cur.st_size else 0
        elif os.path.exists(rotated) and os.stat(rotated).st_ino == seen["inode"]:
            with open(rotated, "rb") as f:
                f.seek(seen["offset"])
                data += f.read(MAX_BATCH)
    with open(path, "rb") as f:
        f.seek(offset)
        chunk = f.read(MAX_BATCH)
    end = chunk.rfind(b"\n") + 1                 # a line still being written waits for the next run
    data += chunk[:end]
    return data.decode("utf-8", errors="replace").splitlines(), {"inode": cur.st_ino, "offset": offset + end}


def _time(text):
    """Purpose: a BIND log time (the container's clock, UTC) as ISO 8601.
    Inputs:  text — e.g. "09-Oct-2026 11:49:42.575".
    Returns: str "2026-10-09T11:49:42.575+00:00", or None when it does not parse.
    Fails:   never.
    Feeds:   _rows."""
    try:
        return datetime.datetime.strptime(text, "%d-%b-%Y %H:%M:%S.%f").replace(
            tzinfo=datetime.timezone.utc).isoformat(timespec="milliseconds")
    except ValueError:
        return None


def _field(value):
    """Purpose: a value as a COPY text field (backslash, tab and newline escaped).
    Inputs:  value — str.
    Returns: str.
    Fails:   never.
    Feeds:   _rows."""
    return value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _rows(lines, pattern, rpz):
    """Purpose: the lines of one log as COPY rows: queries (time, client, port, view, name, type) or rewrites (the
             same and the action and the zone).
    Inputs:  lines — list of str; pattern — QUERY or RPZ; rpz — True for rpz.log's lines.
    Returns: (rows: list of str, skipped: int — lines that are not a query or a rewrite).
    Fails:   never.
    Feeds:   ingest_dns_log."""
    rows, skipped = [], 0
    for line in lines:
        m = pattern.match(line)
        at = _time(m.group(1)) if m else None
        if not at:
            skipped += 1
            continue
        if rpz:
            client, port, _, view, action, name, qtype, via = m.group(2, 3, 4, 5, 6, 7, 8, 9)
            z = ZONE.search(via.rstrip("."))
            row = [at, client, port, view, name.rstrip(".").lower(), qtype, action, z.group(1) if z else via]
        else:
            client, port, _, view, name, qtype = m.group(2, 3, 4, 5, 6, 7)
            row = [at, client, port, view, name.rstrip(".").lower(), qtype]
        rows.append("\t".join(_field(x) for x in row))
    return rows, skipped


def ingest_dns_log(v):
    """Purpose: read the resolver's new query and RPZ log lines into the query log (manual 1.12.2.13, decision
             2.1.12.5): queries in, each rewrite marked on its query, the touched hours' and days' statistics
             recomputed, then rows past their time purged (2.1.12.4: 7 days; statistics 90 days). One run at a time.
    Inputs:  v — rendered vars (install_resolver, install_keycloak, deploy_base_dir).
    Returns: {"off": reason} when the resolver or Postgres is not on; else {"queries": rows added, "rewrites": rewrite
             lines read, "skipped": lines that were neither, "created": True when the database was made now}.
    Fails:   ValidationError from dnslog_psql (Postgres not running or refusing; the place in the files is kept, so
             the next run reads the same lines again); OSError reading the logs or writing the place.
    Feeds:   dns_filter/run_dns_filter_command (`fabricctl dns-filter ingest`, the fabric-dns-log timer),
             dns_filter/read_query_log, dns_filter/dns_filter_stats (before every read); tests/resolver/querylog.py."""
    if not v.get("install_resolver"):
        return {"off": "the BIND resolver is off"}
    if not v.get("install_keycloak"):
        return {"off": "Postgres is not installed (install_keycloak: false)"}
    paths = resolver_paths(v)
    place_file = os.path.join(paths["root"], "ingest.json")
    with open(os.path.join(paths["root"], "ingest.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(place_file) as f:
                place = json.load(f)
        except (OSError, ValueError):
            place = {}
        created = ensure_dnslog_db()
        q_lines, q_place = _new_lines(paths["log"], "query.log", place.get("query.log"))
        r_lines, r_place = _new_lines(paths["log"], "rpz.log", place.get("rpz.log"))
        queries, q_skip = _rows(q_lines, QUERY, False)
        rewrites, r_skip = _rows(r_lines, RPZ, True)
        sql = ["BEGIN;"]
        if queries or rewrites:
            sql += ["CREATE TEMP TABLE q_in (at timestamptz, client inet, port int, view text, name text, qtype text)"
                    " ON COMMIT DROP;",
                    "COPY q_in FROM STDIN;", *queries, "\\.",
                    # a group's view passes what it does not answer to the main view from 127.0.0.1 (1.12.2.15):
                    # that copy is not a client's query
                    "INSERT INTO queries (at, client, port, view, name, qtype) SELECT * FROM q_in"
                    " WHERE client <> '127.0.0.1';",
                    "CREATE TEMP TABLE r_in (at timestamptz, client inet, port int, view text, name text, qtype text,"
                    " action text, zone text) ON COMMIT DROP;",
                    "COPY r_in FROM STDIN;", *rewrites, "\\.",
                    """UPDATE queries q SET action = r.action, zone = r.zone, blocked = (r.action = 'NXDOMAIN')
                       FROM r_in r WHERE q.client = r.client AND q.port = r.port AND q.name = r.name
                       AND q.at BETWEEN r.at - interval '2 seconds' AND r.at + interval '2 seconds';""",
                    # the main view's rewrite for a group's query: on that group query (the same name, no rewrite of
                    # its own, within 2 seconds), so the log names the real client and the list that blocked it
                    """UPDATE queries q SET action = r.action, zone = r.zone, blocked = (r.action = 'NXDOMAIN')
                       FROM r_in r WHERE r.client = '127.0.0.1' AND q.view <> 'everyone' AND q.zone IS NULL
                       AND q.name = r.name
                       AND q.at BETWEEN r.at - interval '2 seconds' AND r.at + interval '2 seconds';""",
                    """CREATE TEMP TABLE touched ON COMMIT DROP AS SELECT DISTINCT date_trunc('hour', at) AS hour
                       FROM (SELECT at FROM q_in UNION ALL SELECT at FROM r_in) t;""",
                    "DELETE FROM stats_hourly WHERE hour IN (SELECT hour FROM touched);",
                    """INSERT INTO stats_hourly SELECT date_trunc('hour', at), '', count(*),
                       count(*) FILTER (WHERE blocked) FROM queries WHERE at >= (SELECT min(hour) FROM touched)
                       AND date_trunc('hour', at) IN (SELECT hour FROM touched) GROUP BY 1;""",
                    """INSERT INTO stats_hourly SELECT date_trunc('hour', at), zone, count(*),
                       count(*) FILTER (WHERE blocked) FROM queries WHERE zone IS NOT NULL
                       AND at >= (SELECT min(hour) FROM touched)
                       AND date_trunc('hour', at) IN (SELECT hour FROM touched) GROUP BY 1, 2;""",
                    """DELETE FROM stats_blocked WHERE day IN
                       (SELECT DISTINCT (hour AT TIME ZONE 'UTC')::date FROM touched);""",
                    """INSERT INTO stats_blocked SELECT (at AT TIME ZONE 'UTC')::date, name, zone, count(*) FROM queries
                       WHERE blocked AND (at AT TIME ZONE 'UTC')::date IN
                       (SELECT DISTINCT (hour AT TIME ZONE 'UTC')::date FROM touched) GROUP BY 1, 2, 3;"""]
        sql += [PURGE, "COMMIT;"]
        dnslog_psql("\n".join(sql) + "\n")
        new = {k: p for k, p in (("query.log", q_place), ("rpz.log", r_place)) if p}
        if new != place:
            write_file_if_changed(place_file, json.dumps(new) + "\n", 0o600)
    return {"queries": len(queries), "rewrites": len(rewrites), "skipped": q_skip + r_skip, "created": created}
