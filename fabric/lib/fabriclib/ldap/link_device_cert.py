from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import DEVICE_NAME_RE, FINGERPRINT_RE

_LINK = r'''
dn = "cn=%s,%s" % (IN["name"], DEV)
op = ldap.MOD_ADD if IN["link"] else ldap.MOD_DELETE
try:
    c.modify_s(dn, [(op, "fabricCertFingerprint", [IN["fp"].encode()])])
except (ldap.TYPE_OR_VALUE_EXISTS, ldap.NO_SUCH_ATTRIBUTE):
    pass
out({"ok": True})
'''


def link_device_cert(v, actor, name, fingerprint, link=True, source="web"):
    """Record (link=True) or forget a certificate's SHA-256 fingerprint on a
    device, so 802.1X EAP-TLS can tell which device a certificate belongs
    to. Idempotent."""
    fp = str(fingerprint).strip().upper()
    if not DEVICE_NAME_RE.match(str(name)):
        raise ValidationError(f"invalid device name: {name!r}")
    if not FINGERPRINT_RE.match(fp):
        raise ValidationError("not a SHA-256 fingerprint")
    run_dirsrv(v, _LINK, {"name": name, "fp": fp, "link": bool(link)})
    write_audit(actor, "DEVICE_CERT_LINK" if link else "DEVICE_CERT_UNLINK", f"device={name} sha256={fp}", source)
