"""FreeRADIUS EAP-TLS `verify { client = ... }` command: record the client
certificate's SHA-256 fingerprint under its serial.

FreeRADIUS writes the certificate to a file only while this command runs
and exposes no fingerprint attribute, but devices are linked to their
certificates by SHA-256 fingerprint. fabric_radius reads the fingerprint
back by TLS-Client-Cert-Serial in the check-eap-tls server. Serials are
unique under the fabric CA (the only one FreeRADIUS accepts). The serial is
read from the certificate itself: FreeRADIUS has not yet put
TLS-Client-Cert-Serial into the request when this runs.

    record_fingerprint.py <certificate file>        exit 0: recorded
"""
import hashlib
import os
import ssl
import sys
import time

CACHE = "/run/freeradius/fp"


def _tlv(der, i):
    """Purpose: read one DER element header.
    Inputs:  der — bytes; i — int offset of the element's tag.
    Returns: (tag int, content start offset, content end offset). Handles short and long length forms.
    Fails:   IndexError if der is truncated at the header.
    Feeds:   serial_of."""
    tag, n = der[i], der[i + 1]
    i += 2
    if n & 0x80:
        count = n & 0x7F
        n = int.from_bytes(der[i:i + count], "big")
        i += count
    return tag, i, i + n


def serial_of(der):
    """Purpose: the certificate's serial number as FreeRADIUS prints TLS-Client-Cert-Serial: lowercase hex
             without leading zero bytes.
    Inputs:  der — bytes, a DER X.509 certificate.
    Returns: str hex serial ("00" for a zero serial).
    Fails:   ValueError("no serial number") if the element after the optional version is not an INTEGER;
             IndexError on truncated DER.
    Feeds:   main."""
    _, cert, _ = _tlv(der, 0)                 # Certificate SEQUENCE
    _, tbs, _ = _tlv(der, cert)               # TBSCertificate SEQUENCE
    tag, start, end = _tlv(der, tbs)
    if tag == 0xA0:                           # [0] version
        tag, start, end = _tlv(der, end)
    if tag != 0x02:
        raise ValueError("no serial number")
    return der[start:end].lstrip(b"\x00").hex() or "00"


def main(path):
    """Purpose: record the presented client certificate's SHA-256 fingerprint under its serial so
             fabric_radius can read it back in check-eap-tls; drop entries older than 10 minutes.
    Inputs:  path — str, the PEM file FreeRADIUS wrote (%{TLS-Client-Cert-Filename}). Writes /run/freeradius/fp.
    Returns: 0 (the process exit status: recorded).
    Fails:   OSError, ValueError (bad PEM or DER); the __main__ wrapper prints the reason and exits 1, and exits 2
             for a wrong argument count — EAP-TLS verification then fails.
    Feeds:   FreeRADIUS mods/eap (tls verify `client = … record_fingerprint.py`); fabric_radius.authorize reads
             the file."""
    with open(path) as f:
        der = ssl.PEM_cert_to_DER_cert(f.read())
    digest = hashlib.sha256(der).hexdigest().upper()
    fp = ":".join(digest[i:i + 2] for i in range(0, 64, 2))
    serial = serial_of(der)
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    tmp = os.path.join(CACHE, f".{serial}.{os.getpid()}")
    with open(tmp, "w") as f:
        f.write(fp)
    os.replace(tmp, os.path.join(CACHE, serial))
    # entries are needed for seconds; drop old ones so the tmpfs never fills
    cutoff = time.time() - 600
    for name in os.listdir(CACHE):
        try:
            if os.stat(os.path.join(CACHE, name)).st_mtime < cutoff:
                os.remove(os.path.join(CACHE, name))
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1]) if len(sys.argv) == 2 else 2)
    except Exception as exc:                  # FreeRADIUS logs stdout: say why
        print(f"record_fingerprint: {type(exc).__name__}: {exc}")
        sys.exit(1)
