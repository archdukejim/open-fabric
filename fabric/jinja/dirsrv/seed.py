#!/usr/bin/env python3
"""Idempotently apply LDIF files to the 389-DS instance in this container.

Run inside the dirsrv container:  python3 /seed/seed.py /seed/*.ldif

* Plain entries are added only when the DN does not exist yet.
* `changetype: modify` records are applied only for attributes whose current
  values differ (case-insensitive), so re-running is a no-op.
* `replace: userPassword` is skipped when the password already binds.
* Prints RESTART_REQUIRED if anything under cn=config changed.

Binds as Directory Manager over LDAPI (a local socket, counted as a secure
channel), using DS_DM_PASSWORD from the container environment.
"""
import base64
import os
import sys
import time

import ldap

LDAPI_URI = "ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket"
DM_DN = "cn=Directory Manager"


def bind_dm(timeout=120):
    """Bind as Directory Manager over LDAPI. On first boot dscontainer reports
    healthy (via autobind) before it has applied DS_DM_PASSWORD, so retry."""
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
    """Yield (dn, changetype, body). body is [(attr, value)] for adds and
    [(op, attr, [values])] for modifies. Handles folding, comments and ::."""
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
    test = ldap.initialize(LDAPI_URI)
    try:
        test.simple_bind_s(dn, password)
        return True
    except ldap.LDAPError:
        return False
    finally:
        test.unbind_s()


def norm(vals):
    return sorted(v.strip().lower() for v in vals)


def main(paths):
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
