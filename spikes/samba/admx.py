"""S0 spike Q13: the core of an ADMX-driven policy editor. Reads an ADMX template and its ADML language file the
way Windows' editor does, lists its policies, and turns chosen values into Registry.pol entries (Samba's own PReg
encoding); can add fabric's root-CA trust in the registry form Windows reads. Runs on the DC (python3-samba).
    python3 admx.py list <admx> <adml>
    python3 admx.py write <admx> <adml> <out Registry.pol> <policy name> <element id>=<value> [--root-ca <cert.pem>]"""
import hashlib
import ssl
import struct
import sys
import xml.etree.ElementTree as ET

from samba.dcerpc import misc, preg
from samba.ndr import ndr_pack



def _local(tag):
    """An element's name without its namespace: Microsoft's templates declare one, Samba's do not."""
    return tag.split("}")[-1]


def _all(root, name):
    return [e for e in root.iter() if _local(e.tag) == name]


def load(admx, adml):
    """Purpose: the policies of an ADMX file with their display names from its ADML.
    Returns: list of {name, display, class, key, elements: [{id, type, key, valueName}]}."""
    strings = {s.get("id"): (s.text or "") for s in _all(ET.parse(adml).getroot(), "string")}
    def text(ref):
        return strings.get(ref[len("$(string."):-1], ref) if ref and ref.startswith("$(string.") else ref
    out = []
    for pol in _all(ET.parse(admx).getroot(), "policy"):
        elements = []
        el = next((c for c in pol if _local(c.tag) == "elements"), None)
        for e in (list(el) if el is not None else []):
            elements.append({"id": e.get("id"), "type": _local(e.tag), "key": e.get("key") or pol.get("key"),
                             "valueName": e.get("valueName")})
        out.append({"name": pol.get("name"), "display": text(pol.get("displayName")), "class": pol.get("class"),
                    "key": pol.get("key"), "elements": elements})
    return out


def entry(key, name, vtype, data):
    e = preg.entry()
    e.keyname, e.valuename, e.type, e.data = key, name, vtype, data
    return e


def root_ca_entries(pem_path):
    """Purpose: fabric's root CA as a trusted root for Windows machines: the registry form the 'Trusted Root
    Certification Authorities' policy writes — SystemCertificates\\Root\\Certificates\\<SHA-1 thumbprint>, value
    Blob: the certificate as a serialized certificate property (id 0x20, the DER)."""
    der = ssl.PEM_cert_to_DER_cert(open(pem_path).read())
    thumb = hashlib.sha1(der).hexdigest().upper()
    blob = struct.pack("<III", 0x20, 1, len(der)) + der
    return [entry(f"Software\\Policies\\Microsoft\\SystemCertificates\\Root\\Certificates\\{thumb}", "Blob",
                  misc.REG_BINARY, blob)]


if __name__ == "__main__":
    cmd, admx, adml = sys.argv[1:4]
    policies = load(admx, adml)
    if cmd == "list":
        for p in policies:
            print(f"{p['name']}\t{p['class']}\t{p['display']}\t" + ",".join(f"{e['type']}:{e['id']}" for e in p["elements"]))
        sys.exit(0)
    out, name, setting = sys.argv[4], sys.argv[5], sys.argv[6]
    eid, value = setting.split("=", 1)
    pol = next(p for p in policies if p["name"] == name)
    el = next(e for e in pol["elements"] if e["id"] == eid)
    entries = [entry(el["key"], el["valueName"], misc.REG_SZ, value)]
    if "--root-ca" in sys.argv:
        entries += root_ca_entries(sys.argv[sys.argv.index("--root-ca") + 1])
    f = preg.file()
    f.header.signature, f.header.version = "PReg", 1
    f.num_entries = len(entries)
    f.entries = entries
    open(out, "wb").write(ndr_pack(f))
    print(f"{pol['display']}: {el['valueName']} = {value}; {len(entries)} entries written to {out}")
