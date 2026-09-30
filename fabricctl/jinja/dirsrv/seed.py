#!/usr/bin/env python3
"""Idempotently apply LDIF files to the 389-DS instance in this container.

Run inside the dirsrv container:  python3 /seed/seed.py /seed/*.ldif

* Plain entries are added only when the DN does not exist yet.
* `changetype: modify` records are applied only for attributes whose current
  values differ (case-insensitive), so re-running is a no-op.
* `replace: userPassword` is skipped when the password already binds.
* `add: attributeTypes` / `objectClasses` on cn=schema are compared by OID
  (the server rewrites definitions), so a definition is added once.
* Prints RESTART_REQUIRED if anything under cn=config changed.

Binds as Directory Manager over LDAPI (a local socket, counted as a secure
channel), using DS_DM_PASSWORD from the container environment.
"""
import base64
import os
import re
import sys
import time

import ldap

LDAPI_URI = "ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket"
DM_DN = "cn=Directory Manager"


def bind_dm(timeout=120):
    """Purpose: bind as Directory Manager over LDAPI, retrying: on first boot dscontainer reports healthy
             (via autobind) before it has applied DS_DM_PASSWORD.
    Inputs:  timeout — seconds to keep retrying, default 120. Reads DS_DM_PASSWORD from the environment.
    Returns: a bound ldap connection (python-ldap LDAPObject).
    Fails:   ldap.INVALID_CREDENTIALS or ldap.SERVER_DOWN after the timeout; KeyError if DS_DM_PASSWORD is unset;
             other LDAP errors at once. Seeding then stops with a traceback (non-zero exit).
    Feeds:   main."""
    deadline = time.time() + timeout
    while True:
        conn = ldap.initialize(LDAPI_URI)
        try:
            conn.simple_bind_s(DM_DN, os.environ["DS_DM_PASSWORD"])
            return conn
        except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
            if time.time() > deadline:
                raise
            time.sleep(3)


def parse_ldif(text):
    """Purpose: parse LDIF text into records (a small parser: folding, comments and base64 "::" values).
    Inputs:  text — str, the LDIF file content.
    Returns: generator of (dn, changetype, body): for "add", body is [(attr, value)]; otherwise body is
             [(op, attr, [values])] with op lower-cased ("replace", "add", "delete"). Base64 values are decoded
             to str with surrogateescape.
    Fails:   binascii.Error on bad base64; IndexError for a record with no lines after comment removal.
             Comments inside a folded line and "<" URL values are not supported.
    Feeds:   main."""
    lines = []
    for raw in text.splitlines():
        if raw.startswith(" ") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)

    records, current = [], []
    for line in lines + [""]:
        if line.startswith("#"):
            continue
        if line.strip() == "":
            if current:
                records.append(current)
                current = []
            continue
        current.append(line)

    for rec in records:
        pairs = []
        for line in rec:
            if line == "-":
                pairs.append(("-", None))
                continue
            attr, _, value = line.partition(":")
            if value.startswith(":"):
                # surrogateescape round-trips binary values (e.g. jpegPhoto)
                value = base64.b64decode(value[1:].strip()).decode("utf-8", "surrogateescape")
            else:
                value = value.strip()
            pairs.append((attr.strip(), value))
        dn = pairs[0][1]
        rest = pairs[1:]
        if rest and rest[0][0].lower() == "changetype":
            changetype, rest = rest[0][1].lower(), rest[1:]
        else:
            changetype = "add"
        if changetype == "add":
            yield dn, "add", rest
            continue
        mods, op = [], None
        for attr, value in rest:
            if attr == "-":
                op = None
            elif op is None:
                op = (attr.lower(), value, [])
                mods.append(op)
            else:
                op[2].append(value)
        yield dn, changetype, mods


def current_values(conn, dn, attr):
    """Purpose: the current values of one attribute of an entry.
    Inputs:  conn — bound LDAPObject; dn — str; attr — str, matched case-insensitively.
    Returns: list of str values (UTF-8 decoded); [] if the entry has no such attribute; None if the entry does
             not exist.
    Fails:   other ldap.LDAPError from the search; UnicodeDecodeError for a binary value that is not UTF-8.
    Feeds:   main."""
    try:
        res = conn.search_s(dn, ldap.SCOPE_BASE, attrlist=[attr])
    except ldap.NO_SUCH_OBJECT:
        return None
    for _, attrs in res:
        for k, vals in attrs.items():
            if k.lower() == attr.lower():
                return [v.decode() for v in vals]
    return []


def password_ok(dn, password):
    """Purpose: whether a password already binds for a DN, so an unchanged userPassword is not replaced.
    Inputs:  dn — str; password — str (clear text from the LDIF).
    Returns: bool, True when a simple bind over LDAPI succeeds.
    Fails:   never — every LDAP error counts as False (an error from the final unbind would propagate).
    Feeds:   main."""
    test = ldap.initialize(LDAPI_URI)
    try:
        test.simple_bind_s(dn, password)
        return True
    except ldap.LDAPError:
        return False
    finally:
        test.unbind_s()


def norm(vals):
    """Purpose: compare attribute values case- and whitespace-insensitively.
    Inputs:  vals — iterable of str.
    Returns: sorted list of stripped, lower-cased values.
    Fails:   never (AttributeError only for non-str items).
    Feeds:   main."""
    return sorted(v.strip().lower() for v in vals)


OID_RE = re.compile(r"^\(\s*([0-9.]+)")


def oids(vals):
    """Purpose: the OIDs of schema definitions, so an attributeTypes/objectClasses value is added once even
             though the server rewrites its text.
    Inputs:  vals — iterable of str definitions, each "( 1.2.3 … )".
    Returns: set of OID strings; values that do not start with "( <oid>" contribute nothing.
    Fails:   never.
    Feeds:   main."""
    return {m.group(1) for m in (OID_RE.match(v.strip()) for v in vals) if m}


def main(paths):
    """Purpose: idempotently apply LDIF files to this container's 389-DS: add missing entries, apply only
             the modify operations whose values differ, and print RESTART_REQUIRED if anything under cn=config
             changed.
    Inputs:  paths — list of LDIF file paths (applied in sorted order); DS_DM_PASSWORD in the environment.
    Returns: None; prints "+ dn" / "~ dn: attrs" lines and "seed: N added, M modified".
    Fails:   SystemExit with a message for an unsupported changetype or a modify on a missing entry; ldap errors
             (e.g. schema violations) and bind_dm failures propagate as a traceback; exit is non-zero either way.
    Feeds:   run as `python3 /seed/seed.py /seed/*.ldif` by lib/dirsrv.sh (seed) and the dirsrv, freeradius
             and hardening test suites; RESTART_REQUIRED is read by dirsrv.sh."""
    conn = bind_dm()
    added = modified = 0
    restart = False

    for path in sorted(paths):
        with open(path, encoding="utf-8") as f:
            for dn, changetype, body in parse_ldif(f.read()):
                if changetype == "add":
                    entry = {}
                    for attr, value in body:
                        entry.setdefault(attr, []).append(value.encode())
                    try:
                        conn.add_s(dn, list(entry.items()))
                        added += 1
                        print(f"  + {dn}")
                    except ldap.ALREADY_EXISTS:
                        pass
                    continue

                if changetype != "modify":
                    raise SystemExit(f"{path}: unsupported changetype {changetype} for {dn}")

                changes = []
                for op, attr, values in body:
                    have = current_values(conn, dn, attr)
                    if have is None:
                        raise SystemExit(f"{path}: {dn} does not exist")
                    if op == "replace":
                        if attr.lower() == "userpassword":
                            if values and password_ok(dn, values[0]):
                                continue
                        elif norm(have) == norm(values):
                            continue
                        changes.append((ldap.MOD_REPLACE, attr, [v.encode() for v in values]))
                    elif op == "add" and dn.lower() == "cn=schema":
                        known = oids(have)
                        missing = [v for v in values if not oids([v]) <= known]
                        if missing:
                            changes.append((ldap.MOD_ADD, attr, [v.encode() for v in missing]))
                    elif op == "add":
                        missing = [v for v in values if v.strip().lower() not in norm(have)]
                        if missing:
                            changes.append((ldap.MOD_ADD, attr, [v.encode() for v in missing]))
                    elif op == "delete":
                        present = [v for v in values if v.strip().lower() in norm(have)] if values else have
                        if present:
                            changes.append((ldap.MOD_DELETE, attr, [v.encode() for v in present] if values else None))
                if changes:
                    conn.modify_s(dn, changes)
                    modified += 1
                    print(f"  ~ {dn}: {', '.join(c[1] for c in changes)}")
                    if dn.lower().endswith("cn=config"):
                        restart = True

    print(f"seed: {added} added, {modified} modified")
    if restart:
        print("RESTART_REQUIRED")


if __name__ == "__main__":
    main(sys.argv[1:])
