#!/usr/bin/env python3
"""Pin fabric's published images in config/images.lock.yaml (manual 3.14.1.4, decision 2.1.14.4): for each of the
images, the multi-arch digest a publish produced under <tag>, after checking it has both architectures and a valid
signature by fabric's images workflow (the same check hosts make, 2.1.14.6). Needs Docker and network access.

    python3 scripts/images/pin_published.py <tag>        e.g. 0.6.0-rc.1

Commit the changed lock (a reviewed commit): that is what hosts will run.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402
from fabriclib.common.read_published_lock import read_published_lock  # noqa: E402
from fabriclib.images.verify_signature import verify_signature  # noqa: E402

LOCK = os.path.join(REPO, "config", "images.lock.yaml")
PLATFORMS = {"linux/amd64", "linux/arm64"}


def _index(ref):
    """Purpose: the multi-arch index digest of a published tag and the platforms it holds.
    Inputs:  ref — str, "<repo>:<tag>". Runs `docker buildx imagetools inspect`.
    Returns: (digest str, set of "os/arch" str).
    Fails:   ValidationError if the tag cannot be inspected (not published, no network).
    Feeds:   pin_published."""
    res = subprocess.run(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise ValidationError(f"{ref}: cannot inspect ({res.stderr.strip()[-200:]})")
    manifest = json.loads(res.stdout)
    platforms = {f"{m['platform']['os']}/{m['platform']['architecture']}"
                 for m in manifest.get("manifests") or [] if m.get("platform")}
    return manifest["digest"], platforms


def pin_published(tag):
    """Purpose: write the tag and verified digest of every published fabric image into the lock's published section.
    Inputs:  tag — str, the tag a publish produced (the images workflow's summary names it).
    Returns: dict {name: digest} as written; a pinned image loses its `pending` mark.
    Fails:   ValidationError if an image lacks a platform, its tag cannot be inspected or its signature does not
             verify (nothing is written then); OSError writing the lock.
    Feeds:   this script (the release procedure, 3.14.1.4)."""
    lock = read_published_lock(os.path.dirname(LOCK))
    cosign = read_images_lock(os.path.dirname(LOCK))["cosign"]["ref"]
    pinned = {}
    with tempfile.TemporaryDirectory() as tmp:          # check every digest now: nothing remembered from before
        for name, entry in sorted(lock["images"].items()):
            digest, platforms = _index(f"{entry['repo']}:{tag}")
            if not PLATFORMS <= platforms:
                raise ValidationError(f"{name}: {tag} has {sorted(platforms)}, not {sorted(PLATFORMS)}")
            verify_signature(f"{entry['repo']}:{tag}@{digest}", cosign, lock["signer"], lock["issuer"],
                             cache=os.path.join(tmp, "verified.json"))
            pinned[name] = digest
    with open(LOCK) as f:
        text = f.read()
    for name, digest in pinned.items():
        line = re.compile(rf'^(    {name}: +\{{var: \S+, )tag: "[^"]*", digest: "[^"]*"', re.M)
        text, n = line.subn(rf'\g<1>tag: "{tag}", digest: "{digest}"', text)
        if n != 1:
            raise ValidationError(f"{name}: its line in the lock's published section was not found")
        # a pending image (not published before) is pending no longer
        text = re.sub(rf'^(    {name}: +\{{.*?), pending: "[^"]*"', r"\g<1>", text, flags=re.M)
    with open(LOCK, "w") as f:
        f.write(text)
    return pinned


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        for image, value in pin_published(sys.argv[1]).items():
            print(f"pinned {image} {value}")
    except ValidationError as e:
        sys.exit(f"error: {e}")
