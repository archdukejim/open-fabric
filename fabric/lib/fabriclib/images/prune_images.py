import json
import os
import subprocess

from fabriclib.common.read_images_lock import read_images_lock
from fabriclib.images.constants import SERVICES, STATE


def _repo(name):
    for prefix in ("docker.io/library/", "docker.io/"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def prune_images(ctx):
    """Remove old images of the repositories fabric uses (nginx, postgres,
    the bases of its local builds, …): everything not pinned now, not the
    previous image of a service (kept for rollback) and not used by any
    container, fabric's or not. Also removes superseded (dangling) local
    builds. Never touches images of other repositories. Returns the refs
    removed."""
    v = ctx.vars
    repos = {_repo(e["repo"]) for e in read_images_lock(ctx.target_dir).values()}
    keep = {v.get(s["var"]) for s in SERVICES}
    if os.path.exists(STATE):
        with open(STATE) as f:
            keep |= {e.get("previous") for e in json.load(f).values()}
    keep_digests = {r.split("@", 1)[1] for r in keep if r and "@" in r}
    containers = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True).stdout.split()
    used = set(subprocess.run(["docker", "inspect", "-f", "{{.Image}}", *containers], capture_output=True,
                              text=True).stdout.split()) if containers else set()
    ids = subprocess.run(["docker", "image", "ls", "-q", "--no-trunc"], capture_output=True, text=True).stdout.split()
    removed = []
    if ids:
        res = subprocess.run(["docker", "image", "inspect", *sorted(set(ids))], capture_output=True, text=True)
        for img in json.loads(res.stdout or "[]"):
            digests = img.get("RepoDigests") or []
            names = {_repo(d.split("@", 1)[0]) for d in digests} | {_repo(t.rsplit(":", 1)[0])
                                                                     for t in img.get("RepoTags") or []}
            if not names & repos or img["Id"] in used:
                continue
            if any(d.split("@", 1)[1] in keep_digests for d in digests):
                continue
            refs = (img.get("RepoTags") or []) + digests or [img["Id"]]
            if subprocess.run(["docker", "rmi", *refs], capture_output=True).returncode == 0:
                removed.append(", ".join(sorted(digests or refs)))
    subprocess.run(["docker", "image", "prune", "-f", "--filter", "label=org.fabric.base"], capture_output=True)
    return removed
