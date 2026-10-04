"""Who may do what in fabric (design D19). Each permission is a Keycloak
realm role named PREFIX + name ("fabric:dns:write"); each bundle is a
composite realm role of permissions, granted to directory groups. The
fabric-agent checks every request against these (required_permission.py);
the web UI only hides what the user cannot do."""
PREFIX = "fabric:"

PERMISSIONS = {
    "status:read": "see the services' health (Overview)",
    "dns:read": "see zones, records, reverse zones and TSIG key names",
    "dns:write": "add and remove DNS records, apply DNS changes",
    "tsig:manage": "create, rotate and delete TSIG keys",
    "dns:filter": "manage the DNS filter in AdGuard Home's own UI (lists, rules, clients)",
    "dhcp:read": "see DHCP subnets, reservations and leases",
    "dhcp:write": "add and remove DHCP reservations",
    "pki:read": "see the CA and issued certificates; inspect a CSR or certificate",
    "pki:issue": "issue key + certificate pairs, convert to .p12",
    "pki:sign": "sign uploaded CSRs",
    "pki:link-device": "link a certificate to a device",
    "devices:read": "see devices and device roles",
    "devices:enroll": "add devices",
    "devices:admin": "change, disable and delete devices",
    "roles:admin": "create, change and delete device roles",
    "radius:read": "see 802.1X (FreeRADIUS) state",
    "radius:admin": "change 802.1X settings",
    "people:read": "see realm users",
    "people:create": "create realm users",
    "people:reset": "reset a user's sign-in (password, TOTP)",
    "vault:status": "see OpenBao's state and unlock methods",
    "vault:unlock": "add, test, remove unlock methods; rotate the vault key",
    "audit:read": "read the audit log",
    "system:admin": "services, updates and settings",
}

_READ = ["status:read", "dns:read", "dhcp:read", "pki:read", "devices:read", "radius:read", "people:read",
         "vault:status",
         "audit:read"]

# bundle -> permissions. "admin" is the web UI admin role (webui_admin_role, default fabric-admin).
BUNDLES = {
    "admin": sorted(PERMISSIONS),
    "fabric-auditor": _READ,
    "fabric-network-operator": ["status:read", "dns:read", "dns:write", "tsig:manage", "dns:filter", "dhcp:read",
                                "dhcp:write",
                                "pki:read", "vault:status"],
    "fabric-equipment-operator": ["status:read", "dns:read", "pki:read", "pki:link-device", "devices:read",
                                  "devices:enroll", "devices:admin", "roles:admin", "radius:read", "radius:admin"],
    "fabric-pki-operator": ["status:read", "pki:read", "pki:issue", "pki:sign", "pki:link-device", "devices:read"],
    "fabric-helpdesk": ["status:read", "dns:read", "pki:read", "devices:read", "devices:enroll", "people:read",
                        "people:create", "people:reset"],
}
