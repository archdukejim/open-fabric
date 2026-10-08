"""S0 spike Q3/Q9: schema sets as AD schema objects, printed as LDIF for ldbmodify against the DC's sam.ldb, in two
parts — the attributes, then (in a second session, once the schema has been reloaded) the classes that use them.
    python3 ad-schema.py <base DN> fabric|sudo attributes|classes

- fabric: fabric's directory schema (templates/dirsrv/seed/05-schema.ldif.j2). AD accepts no OID component above
  32 bits, so fabric's UUID arc (2.25.<128-bit UUID>) is invalid there; the same UUID under Microsoft's arc for
  extensions without a registered number (1.2.840.113556.1.8000.2554), split as Microsoft's OID generator splits a
  GUID, keeps the identity and fits.
- sudo: sudo's own schema for directory-held rules (its registered arc 1.3.6.1.4.1.15953.9), which Ubuntu no
  longer ships as a file for AD."""
import sys

BASE, SET, PART = sys.argv[1], sys.argv[2], sys.argv[3]
SCHEMA = f"CN=Schema,CN=Configuration,{BASE}"
STRING, BOOL, INT, IA5, TIME = ("2.5.5.12", 64), ("2.5.5.8", 1), ("2.5.5.9", 2), ("2.5.5.5", 22), ("2.5.5.11", 24)
UUID = 204492767351757179914238406906488345409
_h = f"{UUID:032x}"
FABRIC_ARC = "1.2.840.113556.1.8000.2554." + ".".join(str(int(_h[a:b], 16)) for a, b in
                                                       ((0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 26), (26, 32)))
SETS = {
    "fabric": (FABRIC_ARC + ".1", FABRIC_ARC + ".2",
               # name, oid suffix, syntax, single-valued
               [("fabricDeviceType", 1, STRING, True), ("fabricEnabled", 2, BOOL, True),
                ("fabricCertFingerprint", 3, IA5, False), ("fabricPermission", 4, STRING, False),
                ("fabricVlan", 5, INT, True), ("fabricPriority", 6, INT, True), ("fabricRoleName", 7, STRING, False),
                ("fabricSite", 8, STRING, True), ("fabricCidr", 9, IA5, True), ("fabricNetworkKind", 10, STRING, True),
                ("fabricAllowOverlap", 11, STRING, True)],
               # name, oid suffix, category (1 structural, 3 auxiliary), must, may
               [("fabricDevice", 1, 3, [], ["fabricDeviceType", "fabricEnabled", "fabricCertFingerprint"]),
                ("fabricRole", 2, 3, [], ["fabricPermission", "fabricVlan", "fabricPriority"]),
                ("fabricDeviceRoles", 3, 3, [], ["fabricRoleName"]),
                ("fabricNetwork", 4, 1, ["fabricCidr"], ["fabricSite", "fabricVlan", "fabricNetworkKind",
                                                         "fabricAllowOverlap", "description"])]),
    "sudo": ("1.3.6.1.4.1.15953.9.1", "1.3.6.1.4.1.15953.9.2",
             [("sudoUser", 1, IA5, False), ("sudoHost", 2, IA5, False), ("sudoCommand", 3, IA5, False),
              ("sudoRunAs", 4, IA5, False), ("sudoOption", 5, IA5, False), ("sudoRunAsUser", 6, IA5, False),
              ("sudoRunAsGroup", 7, IA5, False), ("sudoNotBefore", 8, TIME, False), ("sudoNotAfter", 9, TIME, False),
              ("sudoOrder", 10, INT, True)],
             [("sudoRole", 1, 1, ["cn"], ["sudoUser", "sudoHost", "sudoCommand", "sudoRunAs", "sudoRunAsUser",
                                          "sudoRunAsGroup", "sudoOption", "sudoNotBefore", "sudoNotAfter",
                                          "sudoOrder", "description"])]),
}
ATTR_ARC, CLASS_ARC, ATTRS, CLASSES = SETS[SET]


def cn(name):
    """fabricDeviceType -> FabricDevice-Type style common name (AD's convention for a schema object)."""
    out = "".join(f"-{c}" if c.isupper() else c for c in name)
    return out[0].upper() + out[1:]


if PART == "attributes":
    for name, n, (syntax, om), single in ATTRS:
        print(f"dn: CN={cn(name)},{SCHEMA}\nobjectClass: top\nobjectClass: attributeSchema\n"
              f"attributeID: {ATTR_ARC}.{n}\nlDAPDisplayName: {name}\nadminDisplayName: {cn(name)}\n"
              f"attributeSyntax: {syntax}\noMSyntax: {om}\nisSingleValued: {'TRUE' if single else 'FALSE'}\n"
              f"searchFlags: 1\n")
else:
    for name, n, category, must, may in CLASSES:
        lines = [f"dn: CN={cn(name)},{SCHEMA}", "objectClass: top", "objectClass: classSchema",
                 f"governsID: {CLASS_ARC}.{n}", f"lDAPDisplayName: {name}", f"adminDisplayName: {cn(name)}",
                 "subClassOf: top", f"objectClassCategory: {category}",
                 f"defaultObjectCategory: CN={cn(name)},{SCHEMA}"]
        lines += [f"mustContain: {a}" for a in must] + [f"mayContain: {a}" for a in may]
        if category == 1:
            # without a default security descriptor an object of the class is readable by admins only:
            # Domain Admins and SYSTEM in full, authenticated users (machines included) may read
            lines += ["possSuperiors: organizationalUnit", "possSuperiors: container",
                      "defaultSecurityDescriptor: D:(A;;RPWPCRCCDCLCLORCWOWDSDDTSW;;;DA)"
                      "(A;;RPWPCRCCDCLCLORCWOWDSDDTSW;;;SY)(A;;RPLCLORC;;;AU)"]
        print("\n".join(lines) + "\n")
print("dn:\nchangetype: modify\nadd: schemaUpdateNow\nschemaUpdateNow: 1\n")
