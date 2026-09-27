import ipaddress
import os
import re

import yaml

from fabriclib.common.console import info, ok
from fabriclib.setup.detect_network import detect_network
from fabriclib.setup.errors import SetupError
from fabriclib.setup.upgrade_vars import upgrade_vars

REQUIRED = ["domain", "hostname", "host_ip", "lan_cidr", "lan_gateway"]
LABELS = {
    "domain": "DNS domain for this network (RFC 8375 suggests home.arpa)",
    "hostname": "Name of this host",
    "host_ip": "LAN IP address of this host",
    "lan_cidr": "LAN subnet (CIDR)",
    "lan_gateway": "LAN gateway (router) IP",
    "friendly_name": "Organisation / network name (used in the CA name)",
    "webui_admin_user": "Username of the first web UI admin (created in LDAP/Keycloak)",
}
ADMIN_RE = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")
HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


def _valid(key, value):
    try:
        if key in ("host_ip", "lan_gateway"):
            ipaddress.IPv4Address(value)
        elif key == "lan_cidr":
            ipaddress.IPv4Network(value, strict=False)
        elif key == "webui_admin_user":
            return bool(ADMIN_RE.match(value)) and value not in ("admin", "root")
        elif key in ("domain", "hostname"):
            return bool(HOST_RE.match(value)) and (key != "hostname" or "." not in value)
        return bool(value)
    except ValueError:
        return False


def _load(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _ask(key, default):
    while True:
        answer = input(f"  {LABELS.get(key, key)} [{default or ''}]: ").strip() or (default or "")
        if _valid(key, answer):
            return answer
        print(f"    not a valid {key}")


def collect_vars(ctx):
    """Return the path of the vars file this install is rendered from.

    --file wins; otherwise an existing install's vars.yaml; otherwise the
    required values are asked for (auto-detected defaults). Missing or
    invalid required values are asked for, or are an error with
    --non-interactive. The result is saved as <config>/fabric.yaml."""
    data = {}
    user_file = ctx.user_vars_file
    repo_vars = os.path.join(os.path.dirname(ctx.source_dir), "custom-vars.yaml")
    user = _load(user_file) if user_file else {}
    if os.path.exists(ctx.vars_file):
        # An existing install's values (incl. DNS records added in the web UI
        # or editor) are the base; a --file only overrides the keys it sets.
        data = _load(ctx.vars_file)
        info(f"current settings from {ctx.vars_file}")
        # Images the admin pinned explicitly (a vars file now or on an earlier
        # run, recorded in image_pins) survive an upgrade; the rest follow the release.
        explicit = {**_load(repo_vars), **user}
        pins = set(data.get("image_pins") or []) | {k for k in explicit if k.startswith("image_")}
        data["image_pins"] = sorted(pins)
        for change in upgrade_vars(data, {k: True for k in pins}):
            info(change)
    elif not user_file and os.path.exists(repo_vars):
        # Fresh install from a checkout with the classic custom-vars.yaml.
        # Never on an existing install: it would undo later edits.
        user_file, user = repo_vars, _load(repo_vars)
    if user_file:
        data.update(user)
        info(f"overrides from {user_file}")

    bad = [k for k in REQUIRED if not _valid(k, str(data.get(k) or ""))]
    if bad:
        if ctx.non_interactive:
            raise SetupError(f"missing or invalid in the vars file: {', '.join(bad)}")
        guess = {**detect_network(), "domain": "home.arpa"}
        print("\n  A few details about this network:")
        for key in bad:
            data[key] = _ask(key, data.get(key) or guess.get(key))
        if not data.get("friendly_name"):
            data["friendly_name"] = _ask("friendly_name", "Home Network")

    # First web UI admin (created by the admin step). Chosen once, then kept.
    if not _valid("webui_admin_user", str(data.get("webui_admin_user") or "")):
        sudo_user = os.environ.get("SUDO_USER", "")
        default = sudo_user if sudo_user != "root" and _valid("webui_admin_user", sudo_user) else "fabricadmin"
        data["webui_admin_user"] = default if ctx.non_interactive else _ask("webui_admin_user", default)

    data["deploy_base_dir"] = ctx.deploy_base
    os.makedirs(ctx.config_dir, mode=0o750, exist_ok=True)
    path = os.path.join(ctx.config_dir, "fabric.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    os.chmod(path, 0o640)
    ctx.vars = data
    ok(f"settings saved to {path}")
    return path
