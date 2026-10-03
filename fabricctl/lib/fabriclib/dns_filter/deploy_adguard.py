import base64
import os

import bcrypt
import yaml

from fabriclib.common.write_file_if_changed import write_file_if_changed
from fabriclib.dns.reverse_zones import reverse_zones
from fabriclib.dns_filter.build_adguard_config import build_adguard_config


def _domains(v, links):
    """Purpose: the zones AdGuard forwards to this site's BIND and always allows: this site's domain, the
             organisation's, the linked sites' (they are secondary zones on this BIND, M4) and the reverse zones.
    Inputs:  v — fabric vars (domain, org_domain and what reverse_zones reads); links — dns_links' result.
    Returns: list of zone names without duplicates, this site's domain first.
    Fails:   errors from reverse_zones on malformed records.
    Feeds:   deploy_adguard."""
    names = [v["domain"], v.get("org_domain") or v["domain"]]
    names += [link["domain"] for link in (links or {}).get("children") or []]
    if (links or {}).get("upstream"):
        names.append(links["upstream"]["domain"])
    names += list(reverse_zones(v)["zones"])
    return list(dict.fromkeys(n for n in names if n))


def deploy_adguard(v, secrets, links, jinja_env):
    """Purpose: Write the DNS filter's files (design dns-filter.md): AdGuard Home's configuration (fabric's keys
             merged into what AdGuard has), oauth2-proxy's settings and secrets, and the nginx snippet that signs
             requests into AdGuard after OIDC.
    Inputs:  v — rendered vars: deploy_base_dir, service_users (adguard, oauth2proxy, nginx), ip_bind9, host_ip,
             lan_cidr, fabric_subnet, domain, org_domain, the adguard_* settings and what the templates use;
             secrets — fabric's secrets: adguard_admin_password, adguard_oidc_secret, adguard_cookie_secret;
             links — dns_links' result (the linked sites' zones); jinja_env — the fabric template environment.
    Returns: {"adguard": bool, "oauth2proxy": bool, "nginx": bool} — which of them changed (restart / reload).
    Fails:   KeyError for missing vars or secrets; OSError; yaml errors reading AdGuard's file; jinja2 errors.
    Feeds:   deploy/deploy_optional_parts (when install_adguard); tests/adguard/run.py.
    Notes:   <base>/adguard/conf and work are the adguard user's (0700); its YAML is 0600 and rewritten only
             when the merge changes its content, so AdGuard's own reformatting never restarts it. The local
             user's bcrypt hash is kept while it still matches the password. oauth2-proxy/secrets.env is root
             0600 (docker reads it); the nginx snippet conf.d/adguard-auth.inc (not *.conf, so it is included
             only in AdGuard's location) is root:nginx 0640."""
    base = os.path.join(v["deploy_base_dir"], "adguard")
    a_uid, a_gid = (int(v["service_users"]["adguard"][k]) for k in ("uid", "gid"))
    o_gid = int(v["service_users"]["oauth2proxy"]["gid"])
    for sub, owner, mode in (("conf", (a_uid, a_gid), 0o700), ("work", (a_uid, a_gid), 0o700),
                             ("oauth2-proxy", (0, o_gid), 0o750)):
        path = os.path.join(base, sub)
        os.makedirs(path, mode=mode, exist_ok=True)
        os.chown(path, *owner)
        os.chmod(path, mode)
    changed = {"adguard": False, "oauth2proxy": False, "nginx": False}

    conf_path = os.path.join(base, "conf", "AdGuardHome.yaml")
    current = None
    if os.path.exists(conf_path):
        with open(conf_path) as f:
            current = yaml.safe_load(f) or None
    password = secrets["adguard_admin_password"].encode()
    old = next((u.get("password", "") for u in (current or {}).get("users") or [] if u.get("name") == "fabric"), "")
    try:
        keep = bool(old) and bcrypt.checkpw(password, old.encode())
    except ValueError:
        keep = False
    pw_hash = old if keep else bcrypt.hashpw(password, bcrypt.gensalt()).decode()
    with open(os.path.join(jinja_env.loader.searchpath[0], "adguard", "AdGuardHome.base.yaml")) as f:
        base_cfg = yaml.safe_load(f)
    new = build_adguard_config(current, base_cfg, v, _domains(v, links), pw_hash)
    if new != current:                         # compared parsed: AdGuard's own formatting is no change
        changed["adguard"] = write_file_if_changed(conf_path, yaml.safe_dump(new, sort_keys=False), 0o600,
                                                   a_uid, a_gid)

    o_dir = os.path.join(base, "oauth2-proxy")
    changed["oauth2proxy"] |= write_file_if_changed(
        os.path.join(o_dir, "oauth2-proxy.cfg"), jinja_env.get_template("adguard/oauth2-proxy.cfg.j2").render(**v),
        0o640, 0, o_gid)
    env = (f"OAUTH2_PROXY_CLIENT_SECRET={secrets['adguard_oidc_secret']}\n"
           f"OAUTH2_PROXY_COOKIE_SECRET={secrets['adguard_cookie_secret']}\n")
    changed["oauth2proxy"] |= write_file_if_changed(os.path.join(o_dir, "secrets.env"), env, 0o600, 0, 0)
    root_ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    if os.path.exists(root_ca):
        with open(root_ca) as f:
            changed["oauth2proxy"] |= write_file_if_changed(os.path.join(o_dir, "root_ca.crt"), f.read(), 0o644, 0, 0)

    n_gid = int(v["service_users"]["nginx"]["gid"])
    basic = base64.b64encode(b"fabric:" + password).decode()
    inc = os.path.join(v["deploy_base_dir"], "nginx", "config", "conf.d", "adguard-auth.inc")
    os.makedirs(os.path.dirname(inc), exist_ok=True)
    changed["nginx"] = write_file_if_changed(
        inc, "# fabric: AdGuard Home's own login, sent only after OIDC sign-in (dns-filter.md §5)\n"
             f'proxy_set_header Authorization "Basic {basic}";\n', 0o640, 0, n_gid)
    return changed
