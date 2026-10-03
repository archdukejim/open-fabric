#!/usr/bin/env python3
"""Inside the sandbox: pretend a newer validated list arrived by changing one
entry of the installed images.lock.yaml.

    python3 set_lock.py <name> <repo> <tag> <digest>
"""
import sys

import yaml

PATH = "/opt/fabric/images.lock.yaml"
name, repo, tag, digest = sys.argv[1:5]
with open(PATH) as f:
    lock = yaml.safe_load(f)
lock["images"][name].update(repo=repo, tag=tag, digest=digest)
with open(PATH, "w") as f:
    yaml.safe_dump(lock, f, sort_keys=False)
