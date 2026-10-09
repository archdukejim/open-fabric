#!/usr/bin/env python3
"""On a fabric host, as root (tests/images/update.sh): read or change what the installed lock validates.

    python3 host_images.py status                  each installed service's image row, as JSON lines
    python3 host_images.py pin <var> <tag> <digest>
                                                   make <tag>@<digest> the validated image of <var> (a new list
                                                   "arrived"), in the lock's images or published section
    python3 host_images.py pinned <var>            the lock's current "tag digest" for <var>
"""
import json
import sys

import yaml

sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.images.image_status import image_status  # noqa: E402
from fabriclib.setup.context import SetupContext  # noqa: E402

LOCK = "/opt/fabric/images.lock.yaml"


def _entry(lock, var):
    """The lock entry whose var is var, in either section; exits when there is none."""
    for section in (lock.get("images") or {}, (lock.get("published") or {}).get("images") or {}):
        for entry in section.values():
            if entry.get("var") == var:
                return entry
    sys.exit(f"no lock entry for {var}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["status"]:
        for row in image_status(SetupContext(deploy_base="/opt").load_state()):
            print(json.dumps(row))
    elif len(args) == 2 and args[0] == "pinned":
        e = _entry(yaml.safe_load(open(LOCK)), args[1])
        print(e.get("tag") or "", e.get("digest") or "")
    elif len(args) == 4 and args[0] == "pin":
        lock = yaml.safe_load(open(LOCK))
        _entry(lock, args[1]).update(tag=args[2], digest=args[3])
        with open(LOCK, "w") as f:
            yaml.safe_dump(lock, f, sort_keys=False)
    else:
        sys.exit(__doc__)
