"""What the pages show: tabs, sections, sub-menus, the permissions that show them."""

# (tab id, path, label, optional feature)
TABS = [
    ("overview", "/", "Overview", False),
    ("bind9", "/bind9", "BIND9 · DNS", False),
    ("kea", "/kea", "Kea · DHCP", True),
    ("stepca", "/stepca", "Step-CA · PKI", False),
    ("dirsrv", "/dirsrv", "389-DS · Directory", False),
    ("freeradius", "/freeradius", "FreeRADIUS · 802.1X", True),
    ("openbao", "/openbao", "OpenBao · Secrets", False),
]
# BIND9 tab sections: (view, label)
FREERADIUS_SECTIONS = [("overview", "Overview"), ("switches", "Connect a switch"), ("windows", "Connect Windows")]
BIND9_SECTIONS = [("forward", "Forward zones"), ("reverse", "Reverse zones"), ("tsig", "TSIG keys")]
# OpenBao tab sections and unlock-method (key slot) types
OPENBAO_SECTIONS = [("status", "Status"), ("unlock", "Unlock methods"), ("secrets", "Secrets"),
                    ("disk", "Disk encryption")]
OPENBAO_VIEWS = {"status", "unlock", "secrets", "disk", "add-security-key", "add-usb", "add-hsm", "rotate", "remove"}
SLOT_TYPES = {
    "local": ("Key file", "On this host's disk. Always present, so no kill switch."),
    "pkcs11": ("Security key", "YubiKey, Nitrokey, SmartCard-HSM or any PKCS#11 token. The key can't be copied."),
    "kmip": ("HSM / key manager", "Any KMIP server on your network. Revoke fabric there to lock the vault."),
    "security-key": ("Security key", "YubiKey, Nitrokey, SmartCard-HSM or any PKCS#11 token. The key can't be copied."),
    "usb": ("USB stick", "A plain or keypad-encrypted stick. Cheap; a plain stick can be copied."),
    "hsm": ("HSM / key manager", "Any KMIP server on your network. Revoke fabric there to lock the vault."),
}
# 389-DS tab sections: (view, label)
DIRSRV_SECTIONS = [("devices", "Devices"), ("roles", "Roles"), ("people", "People")]
# Step-CA tab sub-menu: (view, label)
STEPCA_MENU = [("ca", "Certificate authority"), ("sign", "Sign a CSR"), ("issue", "New key + certificate"),
               ("inspect", "Inspect"), ("convert", "Convert"), ("issued", "Issued")]
STEPCA_VIEWS = {v for v, _ in STEPCA_MENU}
KEY_TYPES = ["RSA-2048", "RSA-3072", "RSA-4096", "EC-P256", "EC-P384"]
TSIG_SCOPES = [("acme-hosts", "Certbot DNS-01 for listed hosts only (TXT)"),
               ("acme-zone", "Certbot DNS-01 for any host in the zone (TXT)"),
               ("any-name", "Any name in the zone, chosen record types")]
TSIG_ANY_TYPES = ["A", "AAAA", "CNAME", "TXT", "SRV", "MX"]
# service -> (what it is, tab)
SERVICES = {
    "nginx": ("Reverse proxy", None), "bind9": ("DNS", "bind9"), "stepca": ("Certificate authority", "stepca"),
    "ldap": ("389-DS directory", "dirsrv"), "postgres": ("Keycloak database", None),
    "keycloak": ("Single sign-on", None), "openbao": ("Secrets", "openbao"), "kea": ("DHCP", "kea"),
    "freeradius": ("802.1X", "freeradius"), "samba": ("Windows domain (Samba AD)", None),
    "fabric-web": ("This web UI", None), "fabric-agent": ("Host API", None),
}
# every permission a page asks about (the dev preview's fallback when it runs without fabriclib)
PREVIEW_PERMS = ["status:read", "dns:read", "dns:write", "tsig:manage", "dhcp:read", "dhcp:write", "pki:read",
                 "pki:issue", "pki:sign",
                 "pki:link-device", "devices:read", "devices:enroll", "devices:admin", "roles:admin", "radius:read",
                 "radius:admin",
                 "people:read", "vault:status", "vault:unlock", "audit:read"]
# tab -> the permission(s) that show it (any of them)
TAB_PERMS = {"overview": ("status:read",), "bind9": ("dns:read",), "kea": ("dhcp:read",), "stepca": ("pki:read",),
             "dirsrv": ("devices:read", "people:read"), "freeradius": ("radius:read",),
             "openbao": ("vault:status",)}
MENU_PERMS = {"sign": "pki:sign", "issue": "pki:issue", "convert": "pki:issue", "people": "people:read",
              "devices": "devices:read", "roles": "devices:read", "unlock": "vault:status", "disk": "vault:status"}
