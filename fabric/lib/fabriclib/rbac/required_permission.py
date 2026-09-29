# fabric-agent routes -> the permission they need. A route not listed here is
# refused (default deny). "session" = any signed-in fabric user.
GET = {
    ("version",): "session",
    ("services",): "status:read",
    ("zones",): "dns:read", ("zones", "*"): "dns:read", ("reverse-zones",): "dns:read", ("tsig",): "dns:read",
    ("audit",): "audit:read",
    ("dhcp",): "dhcp:read",
    ("pki", "ca"): "pki:read", ("pki", "issued"): "pki:read",
    ("devices",): "devices:read",
    ("people",): "people:read",
    ("vault",): "vault:status", ("vault", "slots"): "vault:status", ("vault", "devices"): "vault:status",
}
POST = {
    ("events",): "session",
    ("zones", "*", "records"): "dns:write", ("zones", "*", "records", "delete"): "dns:write",
    ("apply",): "dns:write",
    ("pki", "describe-csr"): "pki:read", ("pki", "inspect"): "pki:read",
    ("pki", "sign"): "pki:sign", ("pki", "issue"): "pki:issue", ("pki", "convert"): "pki:issue",
    ("tsig",): "tsig:manage", ("tsig", "*", "rotate"): "tsig:manage", ("tsig", "*", "delete"): "tsig:manage",
    ("vault", "rotate"): "vault:unlock", ("vault", "slots", "add-usb"): "vault:unlock",
    ("vault", "slots", "add-security-key"): "vault:unlock", ("vault", "slots", "add-hsm"): "vault:unlock",
    ("vault", "slots", "*", "test"): "vault:unlock", ("vault", "slots", "*", "remove"): "vault:unlock",
    ("devices",): "devices:enroll", ("devices", "*"): "devices:admin", ("devices", "*", "delete"): "devices:admin",
    ("devices", "*", "certs"): "pki:link-device",
    ("roles",): "roles:admin", ("roles", "*"): "roles:admin", ("roles", "*", "delete"): "roles:admin",
    ("people",): "people:create", ("people", "*", "reset"): "people:reset",
    ("dhcp", "reservations"): "dhcp:write", ("dhcp", "reservations", "*", "delete"): "dhcp:write",
}


def required_permission(method, route):
    """The permission an agent request needs, or None if the route is not
    allowed at all. `route` is the path after /v1/ as a list; "*" in the
    table matches one name segment. Literal entries win over wildcards."""
    table = GET if method == "GET" else POST if method == "POST" else {}
    route = tuple(route)
    if route in table:
        return table[route]
    for pattern, perm in table.items():
        if len(pattern) == len(route) and all(p == "*" or p == r for p, r in zip(pattern, route)):
            return perm
    return None
