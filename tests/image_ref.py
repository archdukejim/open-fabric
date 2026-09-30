#!/usr/bin/env python3
"""Print the validated, digest-pinned ref of one image from
fabric/images.lock.yaml, so every suite tests exactly what fabric runs:

    docker run "$(python3 tests/image_ref.py nginx)" …
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[0:0] = [os.path.join(REPO, "fabricctl", "lib"), REPO]
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402

print(read_images_lock(os.path.join(REPO, "fabricctl"))[sys.argv[1]]["ref"])
