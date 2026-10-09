import json
import os
import time

import yaml

from fabriclib.dns_filter.import_adguard_settings import import_adguard_settings

ADGUARD_KEYS = ("adguard_upstreams", "adguard_filter_lists", "adguard_rules", "adguard_mem_limit", "ip_adguard",
                "ip_oauth2proxy", "cname_adguard", "hostname_adguard", "install_adguard")


def move_dns_filter(data, deploy_base, config_dir):
    """Purpose: move an install's DNS filter from AdGuard Home to the BIND resolver (0.7, decision 2.1.12.3; manual
             2.3.12.1.9): AdGuard's settings — read from its own configuration when it ran, else from the adguard_*
             vars — become the dns_filter_* settings; the adguard_* keys go; what could not move is listed and kept,
             with AdGuard's configuration, in <config>/dns-filter-import-<time>.json.
    Inputs:  data — the vars being collected (changed in place); deploy_base — the install root (AdGuard's
             configuration: <base>/adguard/conf/AdGuardHome.yaml); config_dir — fabric's config folder.
    Returns: list of lines to show (empty when there was nothing to move: dns_filter is none or bind, or unset on a
             host where AdGuard never ran).
    Fails:   OSError writing the import file; yaml errors reading AdGuard's configuration.
    Feeds:   setup/collect_vars (an existing install's vars, and a --file's).
    Notes:   dns_filter_* settings the admin already set are kept as they are. The import file holds no secret:
             AdGuard's local user (its password hash) is left out."""
    filt = str(data.get("dns_filter") or "").strip().lower()
    conf = os.path.join(deploy_base, "adguard", "conf", "AdGuardHome.yaml")
    if filt not in ("adguard", "") or (filt == "" and not os.path.exists(conf)):
        return []
    cfg = None
    if os.path.exists(conf):
        with open(conf) as f:
            cfg = yaml.safe_load(f) or None
    result = import_adguard_settings(cfg, data)
    kept = []
    for key, value in result["settings"].items():
        if key == "dns_filter" or key not in data:
            data[key] = value
        else:
            kept.append(key)
    for key in ADGUARD_KEYS:
        data.pop(key, None)
    record = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "from": conf if cfg else "the adguard_* settings",
              "imported": result["settings"], "kept_as_set": kept, "not_carried": result["not_carried"],
              "clients": result["clients"],
              "adguard_config": {k: val for k, val in (cfg or {}).items() if k not in ("users", "http")}}
    os.makedirs(config_dir, exist_ok=True)
    path = os.path.join(config_dir, f"dns-filter-import-{time.strftime('%Y%m%d-%H%M%S')}.json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(record, f, indent=1, default=str)
    s = result["settings"]
    lines = [f"DNS filter: AdGuard Home → the BIND resolver (0.7): {len(s['dns_filter_lists'])} lists, "
             f"{len(s['dns_filter_allow'])} allowed and {len(s['dns_filter_block'])} blocked names, "
             f"{len(s['dns_filter_upstreams'])} DoT upstreams moved"]
    lines += [f"  kept as you set it: {k}" for k in kept]
    lines += [f"  not moved: {item}" for item in result["not_carried"]]
    lines.append(f"  the record (and AdGuard's configuration): {path}")
    return lines
