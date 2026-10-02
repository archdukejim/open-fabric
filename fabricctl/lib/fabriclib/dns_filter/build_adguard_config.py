import copy
import re

GENERATED_END = "! fabric: the rules above are generated (fabric's own names stay resolvable)"
SETTING_END = "! fabric: the rules above are adguard_rules (vars); rules you add in this UI go below"
DNS_PORT, HTTP_PORT = 5300, 3000          # inside the container; Docker publishes host_ip:53 to DNS_PORT


def build_adguard_config(current, base, v, domains, password_hash):
    """Purpose: AdGuard Home's configuration with fabric's keys set and everything else left to AdGuard's UI
             (design dns-filter.md §3): out of the box AdGuard points at local DNS only (this site's BIND); the
             internet upstreams, bootstrap servers and filter lists are set up in AdGuard's UI after the OIDC
             sign-in, and survive every deploy.
    Inputs:  current — the parsed AdGuardHome.yaml AdGuard runs with (None on a first deploy); base — the parsed
             starting configuration (jinja/adguard/AdGuardHome.base.yaml) used when current is None; v — fabric
             vars: ip_bind9, host_ip, lan_cidr, fabric_subnet, security.firewall_allow, adguard_rules, and — for
             a first deploy only — adguard_upstreams and adguard_filter_lists; domains — the fabric zones AdGuard
             forwards to BIND and always allows (this site's, the organisation's, linked sites', reverse zones);
             password_hash — bcrypt hash of AdGuard's local user "fabric" (nginx sends it after OIDC sign-in).
    Returns: the new configuration (dict); current is not modified.
    Fails:   KeyError for missing vars; TypeError for a malformed current file.
    Feeds:   deploy_adguard.
    Notes:   upstream_dns: fabric's "[/<zone>/]<ip_bind9>" lines first (kept in step with the zones: stale ones
             to BIND are dropped), then every other line as AdGuard has it. On a first deploy those other
             lines are adguard_upstreams, or — when it is empty — <ip_bind9> alone (local DNS only).
             user_rules: generated rules, GENERATED_END, adguard_rules, SETTING_END, then the rules added in the
             UI (on a first deploy over an existing configuration without the markers, every rule that is not
             generated or in adguard_rules counts as added in the UI). filters: adguard_filter_lists, only on a
             first deploy."""
    first = not current
    cfg = copy.deepcopy(current if current else base)
    ip_bind = v["ip_bind9"]
    cfg.setdefault("http", {})["address"] = f"0.0.0.0:{HTTP_PORT}"
    dns = cfg.setdefault("dns", {})
    ours = [f"[/{d}/]{ip_bind}" for d in domains]
    fabric_line = re.compile(r"^\[/[^\]]+/\]" + re.escape(ip_bind) + r"$")
    if first:
        others = list(v.get("adguard_upstreams") or []) or [ip_bind]
    else:
        others = [u for u in dns.get("upstream_dns") or [] if not fabric_line.match(str(u))]
    dns.update({
        "bind_hosts": ["0.0.0.0"], "port": DNS_PORT,
        "upstream_dns": ours + others,
        "allowed_clients": list(dict.fromkeys([v["lan_cidr"], v["fabric_subnet"],
                                               *((v.get("security") or {}).get("firewall_allow") or [])])),
        "use_private_ptr_resolvers": True, "local_ptr_upstreams": [ip_bind],
        "trusted_proxies": ["127.0.0.0/8", "::1/128", v["fabric_subnet"]],
    })
    cfg["users"] = [{"name": "fabric", "password": password_hash}]
    cfg.setdefault("dhcp", {})["enabled"] = False
    cfg.setdefault("tls", {})["enabled"] = False

    generated = [f"@@||{d}^$important" for d in domains] + [f"@@||{v['host_ip']}^$important"]
    setting = list(v.get("adguard_rules") or [])
    rules = list((current or {}).get("user_rules") or [])
    if SETTING_END in rules:
        ui = rules[rules.index(SETTING_END) + 1:]
    else:
        ui = [r for r in rules if r not in generated and r not in setting and r != GENERATED_END]
    cfg["user_rules"] = generated + [GENERATED_END] + setting + [SETTING_END] + ui

    if first and v.get("adguard_filter_lists"):
        cfg["filters"] = [{"enabled": True, "url": f["url"], "name": f["name"], "id": i}
                          for i, f in enumerate(v["adguard_filter_lists"], start=1)]
    return cfg
