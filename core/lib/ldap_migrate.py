#!/usr/bin/env python3
"""Merge an OpenLDAP slapcat export into a 389-DS backend export, producing
an LDIF for `dsconf backend import`. Runs INSIDE the dirsrv container (see
ldap_migrate.sh); reuses the LDIF parser from seed.py.

    python3 - <openldap.ldif> <current-389.ldif> <out.ldif>

Why an offline-style import rather than LDAP adds: 389-DS always generates
entryUUID on an LDAP add (and refuses to modify it), but keeps it on import.
Keycloak links federated users by entryUUID, so it must survive.

* Structural entries (suffix, OUs) and the seeded role accounts already in
  389-DS win — they carry the fresh secrets.
* The osixia bootstrap admin (cn=admin,<base>) is dropped, including from
  group membership.
* Operational attributes are stripped, except entryUUID.
* Groups present on both sides get their `member` values merged.
* Password hashes ({SSHA}, {CRYPT}...) are kept as-is; 389-DS verifies them
  and re-hashes to PBKDF2-SHA512 on the next successful bind.
Prints NOTHING_TO_IMPORT when the 389-DS side already has everything.
"""
import sys

sys.path.insert(0, "/seed")
from seed import parse_ldif  # noqa: E402

OPERATIONAL = {
    "structuralobjectclass", "entrycsn", "createtimestamp", "creatorsname", "modifytimestamp",
    "modifiersname", "entrydn", "subschemasubentry", "hassubordinates", "contextcsn", "memberof",
    "pwdchangedtime", "pwdfailuretime", "pwdaccountlockedtime", "pwdhistory", "pwdpolicysubentry",
}


def load(path):
    with open(path, encoding="utf-8", errors="surrogateescape") as f:
        text = f.read()
    if text.startswith("version:"):
        text = text.split("\n", 1)[1]
    entries = {}
    for dn, changetype, body in parse_ldif(text):
        if changetype == "add":
            attrs = {}
            for attr, value in body:
                attrs.setdefault(attr, []).append(value)
            entries[dn.lower()] = (dn, attrs)
    return entries


def attr_get(attrs, name):
    for k, v in attrs.items():
        if k.lower() == name:
            return k, v
    return None, []


def write_ldif(out, dn, attrs):
    import base64

    def line(attr, value):
        raw = value.encode("utf-8", "surrogateescape")
        safe = raw and raw.isascii() and raw[:1] not in (b" ", b":", b"<") and not raw.endswith(b" ") \
            and b"\n" not in raw and b"\r" not in raw and b"\x00" not in raw
        return f"{attr}: {value}\n" if safe else f"{attr}:: {base64.b64encode(raw).decode()}\n"

    out.write(line("dn", dn))
    for attr, values in attrs.items():
        for v in values:
            out.write(line(attr, v))
    out.write("\n")


def main(old_path, current_path, out_path):
    current = load(current_path)
    old = load(old_path)
    base = min((dn for dn, _ in current.values()), key=lambda d: d.count(","))
    base_l = base.lower()
    admin_l = f"cn=admin,{base_l}"
    role_suffix = f",ou=admins,ou=accounts,{base_l}"

    added = merged = skipped = 0
    for key, (dn, attrs) in sorted(old.items(), key=lambda kv: kv[0].count(",")):
        if key in (base_l, admin_l) or key.endswith(role_suffix) or not key.endswith(base_l):
            skipped += 1
            continue
        clean = {}
        for attr, values in attrs.items():
            if attr.lower() in OPERATIONAL:
                continue
            if attr.lower() == "member":
                values = [v for v in values if v.lower() != admin_l]
                if not values:
                    continue
            clean[attr] = values

        if key not in current:
            current[key] = (dn, clean)
            added += 1
            continue
        _, have = current[key]
        _, classes = attr_get(have, "objectclass")
        _, members = attr_get(clean, "member")
        if "groupofnames" in {c.lower() for c in classes} and members:
            mkey, have_members = attr_get(have, "member")
            missing = [m for m in members if m.lower() not in {h.lower() for h in have_members}]
            if missing:
                have[mkey or "member"] = have_members + missing
                merged += 1
                continue
        skipped += 1

    print(f"migrate: {added} added, {merged} groups merged, {skipped} skipped")
    if not added and not merged:
        print("NOTHING_TO_IMPORT")
        return
    with open(out_path, "w", encoding="utf-8", errors="surrogateescape") as out:
        out.write("version: 1\n\n")
        for _, (dn, attrs) in sorted(current.items(), key=lambda kv: kv[0].count(",")):
            write_ldif(out, dn, attrs)


if __name__ == "__main__":
    main(*sys.argv[1:4])
