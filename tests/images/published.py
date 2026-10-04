"""fabric's published images on hosts (manual 2.6.3): which image a host runs, rendered through the real templates.
Run by tests/images/run.sh; no Docker needed.

- the lock as it is (no digests): every one of the eight compose files builds locally, as before D41
- a lock with digests: each names its published image and has no build section; the Kea check uses it too
- custom ids for an account: that image is built locally again (D80); images without an account are not affected
- the lock's ids equal the Dockerfiles' defaults and vars.yaml.j2's default service accounts
- the rule itself (published_image) and the relaxed-settings list
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.common.read_published_lock import read_published_lock  # noqa: E402
from fabriclib.dhcp.common.kea_image import kea_image  # noqa: E402
from fabriclib.images.effective_service import effective_service  # noqa: E402
from fabriclib.images.constants import SERVICES  # noqa: E402
from fabriclib.images.published_image import published_image  # noqa: E402
from fabriclib.system.relaxed_settings import relaxed_settings  # noqa: E402

IMAGES = ["adguard", "bind9", "dirsrv", "freeradius", "kea", "keycloak", "stepca", "webui"]
PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


def render(templates, out, test_vars=None):
    env = dict(os.environ, FABRIC_TEST_TEMPLATES=templates, FABRIC_TEST_VARS=json.dumps(test_vars or {}))
    res = subprocess.run([sys.executable, os.path.join(REPO, "tests", "render.py"), out], env=env,
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout[-1500:], res.stderr[-1500:])
    return {name: yaml.safe_load(open(os.path.join(out, name, "docker-compose.yml")))["services"] for name in IMAGES}


def images_of(services):
    return {svc["image"] for svc in services.values()}


def builds(services):
    return any("build" in svc for svc in services.values())


work = tempfile.mkdtemp(prefix="fabric-published-")
try:
    # the lock as it is: nothing published yet in this checkout, every image built locally
    lock = read_published_lock(os.path.join(REPO, "config"))
    unpublished = [n for n in IMAGES if not lock["images"][n]["ref"]]
    plain = render(os.path.join(REPO, "templates"), os.path.join(work, "plain"))
    if unpublished == IMAGES:
        check("without published digests every image builds locally, as before",
              all(builds(plain[n]) and all(i.startswith("fabric/") for i in images_of(plain[n])) for n in IMAGES),
              {n: sorted(images_of(plain[n])) for n in IMAGES})
    else:
        check("the lock pins a published digest for every image (none half-published)", not unpublished, unpublished)

    # a lock with every image published (fake digests: rendering never pulls)
    tree = os.path.join(work, "tree")
    os.makedirs(os.path.join(tree, "config"))
    os.symlink(os.path.join(REPO, "templates"), os.path.join(tree, "templates"))
    text = open(os.path.join(REPO, "config", "images.lock.yaml")).read()
    for i, name in enumerate(IMAGES):
        digest = "sha256:" + f"{i + 1:x}" * 64
        text = re.sub(rf'^(    {name}: +\{{var: \S+, )tag: "[^"]*", digest: "[^"]*"',
                      rf'\g<1>tag: "9.9.9-rc.1", digest: "{digest}"', text, flags=re.M)
    open(os.path.join(tree, "config", "images.lock.yaml"), "w").write(text)
    published = read_published_lock(os.path.join(tree, "config"))["images"]
    refs = {n: published[n]["ref"] for n in IMAGES}
    check("the test lock pins all eight", all(refs.values()), refs)
    pub = render(os.path.join(tree, "templates"), os.path.join(work, "published"))
    for n in IMAGES:
        check(f"{n}: a default host runs the published image ({refs[n].split('@')[0]}) and builds nothing",
              images_of(pub[n]) == {refs[n]} and not builds(pub[n]), sorted(images_of(pub[n])))
    rendered_vars = yaml.safe_load(open(os.path.join(work, "published", "vars.yaml")))
    check("the Kea configuration check uses the published Kea image",
          kea_image(jinja_env(os.path.join(tree, "templates")), rendered_vars) == refs["kea"])
    check("vars.yaml carries image_fabric_* and the cosign pin, the signature check on by default",
          all(rendered_vars[f"image_fabric_{n}"] == refs[n] for n in IMAGES)
          and "@sha256:" in rendered_vars["image_cosign"] and rendered_vars["image_signature_check"] is True)

    # custom ids for the DNS account: bind9 is built locally (its ids are baked in); stepca (no account) is not
    users = {"bind": {"uid": 700, "gid": 700, "name": "fabric-dns"}}
    custom = render(os.path.join(tree, "templates"), os.path.join(work, "custom"), {"service_users": users})
    check("custom ids for the bind account: bind9 builds locally again (D80)",
          builds(custom["bind9"]) and images_of(custom["bind9"]) == {"fabric/bind9:local"}
          and custom["bind9"]["bind9"]["build"]["args"]["BIND_UID"] == "700")
    check("custom bind ids leave the images without that account published",
          images_of(custom["stepca"]) == {refs["stepca"]} and images_of(custom["dirsrv"]) == {refs["dirsrv"]})

    # the lock's ids are what the Dockerfiles bake in and what vars.yaml.j2 gives by default
    defaults = yaml.safe_load(open(os.path.join(work, "plain", "vars.yaml")))["service_users"]
    wrong = []
    for n in IMAGES:
        e = published[n]
        dockerfile = open(os.path.join(REPO, "packaging", "images", n, "Dockerfile")).read()
        args = dict(re.findall(r"^ARG (\w+_[UG]ID)=(\d+)$", dockerfile, re.M))
        baked = f"{next((v for k, v in args.items() if k.endswith('_UID')), '')}:" \
                f"{next((v for k, v in args.items() if k.endswith('_GID')), '')}" if args else ""
        if (e.get("ids") or "") != baked:
            wrong.append(f"{n}: lock {e.get('ids')!r}, Dockerfile {baked!r}")
        if e.get("account"):
            u = defaults[e["account"]]
            if f"{u['uid']}:{u['gid']}" != e["ids"]:
                wrong.append(f"{n}: vars default {u['uid']}:{u['gid']}")
    check("the lock's ids match the Dockerfiles and the default service accounts", not wrong, wrong)

    # the rule and what fabricctl images makes of it
    e = published["bind9"]
    host = {"image_fabric_bind9": refs["bind9"], "service_users": {"bind": {"uid": 600, "gid": 600}}}
    check("published_image: in use for a default host", published_image(host, e) == refs["bind9"])
    check("published_image: refused when not pinned by digest",
          published_image(dict(host, image_fabric_bind9="ghcr.io/x/bind9:1.0"), e) == "")
    check("published_image: refused for other ids or an unset var",
          published_image(dict(host, service_users={"bind": {"uid": 600, "gid": 601}}), e) == ""
          and published_image({"service_users": host["service_users"]}, e) == "")
    svc = next(s for s in SERVICES if s["name"] == "bind9")
    eff = effective_service(svc, host, published)
    check("fabricctl images sees bind9 on its published image (own var, no local build)",
          eff["var"] == "image_fabric_bind9" and eff["build"] is None and svc["build"] == "fabric/bind9:local")
    check("relaxed settings: none by default, the signature opt-out listed when set",
          relaxed_settings({}) == [] and relaxed_settings({"image_signature_check": False})[0]["setting"]
          == "image_signature_check: false")
finally:
    shutil.rmtree(work, ignore_errors=True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
