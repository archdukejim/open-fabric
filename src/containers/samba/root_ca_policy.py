import hashlib
import ssl
import struct

from samba.dcerpc import misc, preg
from samba.ndr import ndr_pack

# the Registry extension and the Certificates tool: what Windows' editor lists for a trusted-root policy
EXTENSIONS = "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{53D6AB1D-2488-11D1-A28C-00C04FB94F17}]"


def root_ca_policy(pem):
    """Purpose: fabric's root CA as a trusted root on every Windows member (S5, D77, manual 2.11.2.9): the Registry.pol
             that Windows' "Trusted Root Certification Authorities" policy writes —
             Software\\Policies\\Microsoft\\SystemCertificates\\Root\\Certificates\\<SHA-1 thumbprint>, value Blob:
             the certificate as a serialized certificate property (id 0x20, its DER) (Q13).
    Inputs:  pem — str, the root CA certificate (PEM).
    Returns: bytes, the Registry.pol file (Samba's PReg encoding).
    Fails:   ValueError for text that is not a PEM certificate.
    Feeds:   converge (the domain's trust GPO)."""
    der = ssl.PEM_cert_to_DER_cert(pem)
    entry = preg.entry()
    entry.keyname = ("Software\\Policies\\Microsoft\\SystemCertificates\\Root\\Certificates\\"
                     + hashlib.sha1(der).hexdigest().upper())
    entry.valuename = "Blob"
    entry.type = misc.REG_BINARY
    entry.data = struct.pack("<III", 0x20, 1, len(der)) + der
    f = preg.file()
    f.header.signature, f.header.version = "PReg", 1
    f.num_entries = 1
    f.entries = [entry]
    return ndr_pack(f)
