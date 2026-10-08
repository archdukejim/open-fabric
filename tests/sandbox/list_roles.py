#!/usr/bin/env python3
"""Inside the sandbox, as root: the device roles' names, one per line (read
with fabric's own directory code)."""
import sys

sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.common.load_vars import load_vars  # noqa: E402
from fabriclib.directory.list_roles import list_roles  # noqa: E402

for role in list_roles(load_vars()):
    print(role["name"])
