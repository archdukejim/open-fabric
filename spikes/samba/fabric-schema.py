"""S0 spike Q3: fabric's directory schema (templates/dirsrv/seed/05-schema.ldif.j2) as AD schema objects, with
OIDs derived from fabric's UUID (see ARC). Prints LDIF for ldbmodify against the DC's sam.ldb, in two parts:
the attributes, then (in a second session, once the schema has been reloaded) the classes that use them.
    python3 fabric-schema.py <base DN> attributes|classes"""
import sys

BASE, PART = sys.argv[1], sys.argv[2]
SCHEMA = f"CN=Schema,CN=Configuration,{BASE}"
# AD accepts no OID component above 32 bits, so fabric's UUID arc (2.25.<128-bit UUID>) is invalid there. The same
# UUID under Microsoft's arc for schema extensions without a registered number (1.2.840.113556.1.8000.2554), split
# the way Microsoft's OID generator splits a GUID, keeps the identity and fits.
UUID = 204492767351757179914238406906488345409
_h = f"{UUID:032x}"
ARC = "1.2.840.113556.1.8000.2554." + ".".join(str(int(_h[a:b], 16)) for a, b in
                                                ((0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 26), (26, 32)))
# name, oid suffix, (attributeSyntax, oMSyntax), single-valued
STRING, BOOL, INT, IA5 = ("2.5.5.12", 64), ("2.5.5.8", 1), ("2.5.5.9", 2), ("2.5.5.5", 22)
ATTRS = [("fabricDeviceType", 1, STRING, True), ("fabricEnabled", 2, BOOL, True),
         ("fabricCertFingerprint", 3, IA5, False), ("fabricPermission", 4, STRING, False),
         ("fabricVlan", 5, INT, True), ("fabricPriority", 6, INT, True), ("fabricRoleName", 7, STRING, False),
         ("fabricSite", 8, STRING, True), ("fabricCidr", 9, IA5, True), ("fabricNetworkKind", 10, STRING, True),
         ("fabricAllowOverlap", 11, STRING, True)]
# name, oid suffix, category (1 structural, 3 auxiliary), must, may
CLASSES = [("fabricDevice", 1, 3, [], ["fabricDeviceType", "fabricEnabled", "fabricCertFingerprint"]),
           ("fabricRole", 2, 3, [], ["fabricPermission", "fabricVlan", "fabricPriority"]),
           ("fabricDeviceRoles", 3, 3, [], ["fabricRoleName"]),
           ("fabricNetwork", 4, 1, ["fabricCidr"], ["fabricSite", "fabricVlan", "fabricNetworkKind",
                                                    "fabricAllowOverlap", "description"])]


def cn(name):
    """fabricDeviceType -> fabric-Device-Type (AD's convention for a schema object's common name)."""
    out = "".join(f"-{c}" if c.isupper() else c for c in name)
    return out[0].upper() + out[1:]


if PART == "attributes":
    for name, n, (syntax, om), single in ATTRS:
        print(f"dn: CN={cn(name)},{SCHEMA}\nobjectClass: top\nobjectClass: attributeSchema\n"
              f"attributeID: {ARC}.1.{n}\nlDAPDisplayName: {name}\nadminDisplayName: {cn(name)}\n"
              f"attributeSyntax: {syntax}\noMSyntax: {om}\nisSingleValued: {'TRUE' if single else 'FALSE'}\n"
              f"searchFlags: 1\n")
    print("dn:\nchangetype: modify\nadd: schemaUpdateNow\nschemaUpdateNow: 1\n")
else:
    for name, n, category, must, may in CLASSES:
        lines = [f"dn: CN={cn(name)},{SCHEMA}", "objectClass: top", "objectClass: classSchema",
                 f"governsID: {ARC}.2.{n}", f"lDAPDisplayName: {name}", f"adminDisplayName: {cn(name)}",
                 "subClassOf: top", f"objectClassCategory: {category}",
                 f"defaultObjectCategory: CN={cn(name)},{SCHEMA}"]
        lines += [f"mustContain: {a}" for a in must] + [f"mayContain: {a}" for a in may]
        if category == 1:
            lines += ["possSuperiors: organizationalUnit", "possSuperiors: container"]
        print("\n".join(lines) + "\n")
    print("dn:\nchangetype: modify\nadd: schemaUpdateNow\nschemaUpdateNow: 1\n")
