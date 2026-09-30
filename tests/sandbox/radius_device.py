#!/usr/bin/env python3
"""Inside the sandbox, as root: a device role granting network:mab on VLAN
30 and a printer with a MAC in it, made by fabric's own directory code (as
the 389-DS tab does). Prints "ok"."""
import sys

sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.common.load_vars import load_vars  # noqa: E402
from fabriclib.ldap.add_device import add_device  # noqa: E402
from fabriclib.ldap.add_role import add_role  # noqa: E402

v = load_vars()
add_role(v, "sandbox", "printers", {"permissions": ["network:mab"], "vlan": "30", "priority": 50}, source="cli")
add_device(v, "sandbox", "sbxprinter", {"type": "printer", "roles": ["printers"], "macs": [sys.argv[1]]}, source="cli")
print("ok")
