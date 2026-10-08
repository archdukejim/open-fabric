"""A person of this site in the domain, made the way fabric makes them (tests/sandbox), optionally in one of the
organisation's groups (e.g. auditors, for a fabric role bundle). Prints "created" or why not (re-runs find them).
    python3 make_person.py <uid> [<group>]                (as root on the fabric host)
"""
import sys

import yaml

sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.directory.create_person import create_person  # noqa: E402
from fabriclib.directory.run_op import run_op  # noqa: E402
from fabriclib.secrets.load_secrets import load_secrets  # noqa: E402

if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)
uid = sys.argv[1]
v = yaml.safe_load(open("/opt/fabric/config/vars.yaml"))
try:
    create_person(v, "test", uid, uid.title(), "Test", f"{uid}@lan.test", source="test")
    print("created")
except ValidationError as e:
    print(f"{uid}: {e}")
if len(sys.argv) == 3:
    run_op(v, load_secrets(v=v), "add_group_member", {"group": sys.argv[2], "uid": uid})
    print(f"in {sys.argv[2]}")
