import ipaddress
import os
import re

import yaml

from fabriclib.common.console import info, ok
from fabriclib.common.errors import ValidationError
from fabriclib.deploy.check_samba_settings import POLICY_KEYS
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.decode_invitation import decode_invitation
from fabriclib.setup.detect_network import detect_network
from fabriclib.secrets.save_secrets import save_secrets
from fabriclib.setup.ask_ad_domain import ask_ad_domain
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
HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                     r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


def _valid(key, value):
    """Purpose: check one answer or vars value for a required or asked setting.
    Inputs:  key — setting name (host_ip, lan_gateway, lan_cidr, webui_admin_user, domain, hostname, or other);
             value — str.
    Returns: True if valid: IPv4 address, IPv4 network, an admin username matching ADMIN_RE that is not
             "admin"/"root", a DNS name (hostname without dots); any other key just needs a non-empty value.
    Fails:   never — ValueError from ipaddress is turned into False.
    Feeds:   collect_vars (which required values to ask), _ask."""
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
    """Purpose: read a YAML vars file if it exists.
    Inputs:  path — file path or None/"".
    Returns: the parsed dict; {} when path is empty, missing or the file is empty.
    Fails:   OSError if unreadable; yaml.YAMLError if it does not parse.
    Feeds:   collect_vars."""
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _ask(key, default):
    """Purpose: prompt until the operator gives a valid value for one setting.
    Inputs:  key — setting name (label from LABELS); default — offered value (Enter accepts it) or None.
    Returns: the valid answer (str).
    Fails:   EOFError from input() when stdin is closed; loops forever on invalid input by design.
    Feeds:   collect_vars."""
    while True:
        answer = input(f"  {LABELS.get(key, key)} [{default or ''}]: ").strip() or (default or "")
        if _valid(key, answer):
            return answer
        print(f"    not a valid {key}")


def _join_defaults(ctx, data):
    """Purpose: settings a site joining an upstream (setup --join) starts from: the invitation's site name and
             organisation domain, and a domain of its own, by default <site>.<organisation domain>.
    Inputs:  ctx — SetupContext: join_invitation, vars_file, config_dir; data — the settings so far (changed).
    Returns: None; data gets site_name, org_domain, ldap_base_dn, (unless set) domain and, from an invitation made
             on the root site, ad_domain, ad_password_policy and ad_dc_type (so setup asks neither).
    Fails:   SetupError when the invitation is damaged (decode_invitation), when this host already has a fabric
             that is not a member of that upstream (only fresh installs join: design F1), or when site_name is
             set to another name than the invitation's.
    Feeds:   collect_vars."""
    try:
        inv = decode_invitation(ctx.join_invitation)
    except ValidationError as e:
        raise SetupError(str(e)) from None
    upstream = load_registry(os.path.join(ctx.config_dir, "federation.yaml"))["upstream"]
    if os.path.exists(ctx.vars_file) and not (upstream and upstream.get("site_name") == inv["upstream"]):
        raise SetupError("only a fresh install can join a fabric: this host already has one "
                         "(fabricctl uninstall first, or invite it later when existing installs can join)")
    if data.get("site_name") and str(data["site_name"]).lower() != inv["site"]:
        raise SetupError(f"the invitation is for site {inv['site']}, but site_name is {data['site_name']}")
    data["site_name"], data["org_domain"], data["ldap_base_dn"] = inv["site"], inv["org_domain"], inv["ldap_base_dn"]
    if not data.get("domain"):
        data["domain"] = f"{inv['site']}.{inv['org_domain']}"
    if inv["dc"]:                            # the root's domain: this site's DC joins it (manual 1.8.8.4)
        data["ad_domain"], data["ad_password_policy"] = inv["ad_domain"], inv["ad_password_policy"]
        data["ad_dc_type"] = inv["dc"]
    info(f"joining {inv['upstream']} ({inv['org_domain']}) as site {inv['site']}, domain {data['domain']}")


def collect_vars(ctx):
    """Purpose: work out the settings this install is rendered from and save them as <config>/fabric.yaml.
    Inputs:  ctx — SetupContext: user_vars_file (--file), join_invitation (--join: _join_defaults), non_interactive,
             vars_file (existing install),
             source_dir (a checkout's ../custom-vars.yaml), config_dir, secrets_file, deploy_base;
             env SUDO_USER (default admin name).
    Returns: path of fabric.yaml (str). Leaves ctx.vars = the data written. Precedence: an existing
             vars.yaml is the base and --file overrides the keys it sets; on a fresh install without --file a
             checkout's custom-vars.yaml is used. Existing installs keep their digest-pinned images
             (upgrade_vars); image_* keys set explicitly are recorded in image_pins. Missing/invalid required
             values are asked for (defaults from detect_network); webui_admin_user is chosen once; the AD domain
             and the password policy are asked when missing (ask_ad_domain).
             Embedded TSIG secrets go to the secrets file, never into fabric.yaml.
    Fails:   SetupError for missing/invalid required values (the AD domain and policy included) with
             --non-interactive, invalid tsig_keys, or a
             secrets file that cannot be written (ValidationError converted); OSError/yaml errors on files.
    Feeds:   run_setup main (before choose_plan and the steps); ctx.vars feeds choose_plan and the steps
             before deploy; deploy_config renders from fabric.yaml."""
    data = {}
    user_file = ctx.user_vars_file
    repo_vars = os.path.join(os.path.dirname(ctx.source_dir), "custom-vars.yaml")
    user = _load(user_file) if user_file else {}
    if os.path.exists(ctx.vars_file):
        # An existing install's values (incl. DNS records added in the web UI
        # or editor) are the base; a --file only overrides the keys it sets.
        data = _load(ctx.vars_file)
        info(f"current settings from {ctx.vars_file}")
        # The images this host runs are kept (a fabric upgrade never changes
        # them: `fabricctl images update` does). Images the admin set
        # explicitly (a vars file now or earlier, recorded in image_pins) are
        # also left alone by `images update`.
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

    if ctx.join_invitation:
        _join_defaults(ctx, data)

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

    # The directory (manual 1.6.3): the AD domain and the whole password policy, no defaults (D87, D89)
    policy = data.get("ad_password_policy") or {}
    if not data.get("ad_domain") or not (set(POLICY_KEYS) | {"complexity"}) <= set(policy):
        if ctx.non_interactive:
            raise SetupError("missing in the vars file: ad_domain and every key of ad_password_policy (manual "
                             "2.1.9.7: the directory's domain and password policy have no defaults)")
        ctx.vars = data
        ask_ad_domain(ctx)

    data["deploy_base_dir"] = ctx.deploy_base
    os.makedirs(ctx.config_dir, mode=0o750, exist_ok=True)

    # Embedded TSIG secrets (existing keys whose RFC2136 clients must keep
    # working) go to the 0600 secrets file, never into fabric.yaml/vars.yaml.
    try:
        data["tsig_keys"], embedded = normalize_tsig_keys(data.get("tsig_keys"), data["domain"],
                                                          data.pop("tsig_secrets", None))
    except ValidationError as e:
        raise SetupError(str(e)) from None
    if embedded:
        try:
            save_secrets({"tsig_secrets": embedded}, ctx.secrets_file)
        except ValidationError as e:
            raise SetupError(str(e)) from None
        ok(f"TSIG secrets for {', '.join(sorted(embedded))} stored with fabric's secrets")
    path = os.path.join(ctx.config_dir, "fabric.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    os.chmod(path, 0o640)
    ctx.vars = data
    ok(f"settings saved to {path}")
    return path
