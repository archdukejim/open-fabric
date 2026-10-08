#!/usr/bin/env python3
"""Inside the sandbox, as root: give the default `printers` role (created by
setup, network:mab) VLAN 30 and put a printer with a MAC in it, with
fabric's own directory code (as the 389-DS tab does). Prints "ok"."""
import sys

sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.common.load_vars import load_vars  # noqa: E402
from fabriclib.directory.add_device import add_device  # noqa: E402
from fabriclib.directory.update_role import update_role  # noqa: E402

v = load_vars()
update_role(v, "sandbox", "printers", {"permissions": ["network:mab"], "vlan": "30", "priority": 50,
                                       "description": "Printers: by MAC (MAB)"}, source="cli")
add_device(v, "sandbox", "sbxprinter", {"type": "printer", "roles": ["printers"], "macs": [sys.argv[1]]}, source="cli")
print("ok")
