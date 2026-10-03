#!/usr/bin/env python3
"""`python3 deploy.py`: run the deploy engine (fabriclib/deploy/apply_deployment.py). Kept as an entry point for
setup (fabriclib/setup/deploy_config.py), `fabricctl --apply` (interactive.py) and running it by hand; the engine's
steps live in fabriclib/deploy/."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fabriclib.deploy.apply_deployment import apply_deployment  # noqa: E402,F401

if __name__ == "__main__":
    apply_deployment()
