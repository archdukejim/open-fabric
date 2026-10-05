import os
import subprocess
import uuid

import ldb


def _gpo(samdb, name):
    """Purpose: a GPO found by its display name (fabric's names are its own).
    Inputs:  samdb — SamDB; name — str.
    Returns: (dn str, guid "{…}" str, versionNumber int) or None.
    Fails:   ldb.LdbError from the search.
    Feeds:   ensure_gpo."""
    res = samdb.search(base=f"CN=Policies,CN=System,{samdb.domain_dn()}", scope=ldb.SCOPE_ONELEVEL,
                       expression=f"(&(objectClass=groupPolicyContainer)(displayName={ldb.binary_encode(name)}))",
                       attrs=["cn", "versionNumber"])
    if not res:
        return None
    return str(res[0].dn), str(res[0]["cn"]), int(str(res[0].get("versionNumber", ["0"])[0]))


def ensure_gpo(samdb, lp, name, link_dn, extensions, files, user_extensions=None):
    """Purpose: one of fabric's Group Policy objects as wanted (manual 2.11.2.9): created when missing, linked to its
             target, its files in SYSVOL exactly `files`; a change bumps its version in AD and in GPT.INI so members
             apply it, and SYSVOL's ACLs are reset after writing (Q13, Q16).
    Inputs:  samdb — SamDB; lp — LoadParm (realm, the SYSVOL path); name — display name; link_dn — str, the domain or
             an OU; extensions — gPCMachineExtensionNames value ("[{CSE}{tool}]…", sorted as Windows writes them);
             files — {path under the GPO folder, e.g. "Machine/Registry.pol": bytes}; user_extensions —
             gPCUserExtensionNames for user policies (None: left as it is; "": none).
    Returns: list of str, what was created or changed.
    Fails:   ldb.LdbError from AD; OSError writing SYSVOL; CalledProcessError from `samba-tool ntacl sysvolreset`.
    Feeds:   converge.
    Notes:   made locally on the DC's own database and SYSVOL (no SMB, no credentials), as samba-tool's GPO commands
             make them over the network."""
    base = str(samdb.domain_dn())
    realm = lp.get("realm").lower()
    done = []
    found = _gpo(samdb, name)
    if found is None:
        guid = "{" + str(uuid.uuid4()).upper() + "}"
        dn = f"CN={guid},CN=Policies,CN=System,{base}"
        samdb.add({"dn": dn, "objectClass": "groupPolicyContainer", "displayName": name, "flags": "0",
                   "gPCFunctionalityVersion": "2", "versionNumber": "0",
                   "gPCFileSysPath": f"\\\\{realm}\\SysVol\\{realm}\\Policies\\{guid}"})
        samdb.add({"dn": f"CN=Machine,{dn}", "objectClass": "container"})
        samdb.add({"dn": f"CN=User,{dn}", "objectClass": "container"})
        found = (dn, guid, 0)
        done.append(f"GPO {name} created")
    dn, guid, version = found
    folder = os.path.join(lp.get("path", "sysvol"), realm, "Policies", guid)
    changed = False
    for rel, data in files.items():
        path = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path) or open(path, "rb").read() != data:
            with open(path, "wb") as f:
                f.write(data)
            changed = True
    names = {"gPCMachineExtensionNames": extensions}
    if user_extensions is not None:
        names["gPCUserExtensionNames"] = user_extensions
    ext = samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=list(names))[0]
    if changed or any(str(ext.get(attr, [""])[0]) != want for attr, want in names.items()) \
            or not os.path.exists(os.path.join(folder, "GPT.INI")):
        # a GPO's version: user changes in the high 16 bits, machine changes in the low ones (Windows checks each)
        version += 1 + (0x10000 if user_extensions else 0)
        msg = ldb.Message(ldb.Dn(samdb, dn))
        msg["versionNumber"] = ldb.MessageElement([str(version)], ldb.FLAG_MOD_REPLACE, "versionNumber")
        for attr, want in names.items():         # an empty list removes the attribute: AD keeps no empty values
            msg[attr] = ldb.MessageElement([want] if want else [], ldb.FLAG_MOD_REPLACE, attr)
        samdb.modify(msg)
        with open(os.path.join(folder, "GPT.INI"), "wb") as f:
            f.write(f"[General]\r\nVersion={version}\r\n".encode())
        done.append(f"GPO {name}: version {version}")
    link = f"[LDAP://{dn};0]"
    target = samdb.search(base=link_dn, scope=ldb.SCOPE_BASE, attrs=["gPLink"])[0]
    current = str(target.get("gPLink", [""])[0])
    if dn.lower() not in current.lower():
        samdb.modify(ldb.Message.from_dict(samdb, {"dn": link_dn, "gPLink": current + link}, ldb.FLAG_MOD_REPLACE))
        done.append(f"GPO {name} linked to {link_dn}")
    if done:
        subprocess.run(["samba-tool", "ntacl", "sysvolreset", "-s", lp.configfile], check=True, capture_output=True)
    return done
