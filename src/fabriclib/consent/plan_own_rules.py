from fabriclib.security.firewall_rules import firewall_rules
from fabriclib.security.host_own_rules import host_own_rules
from fabriclib.security.ssh_ports import ssh_ports


def plan_own_rules(v, config_dir):
    """Purpose: the host's own ufw rules securing the host would remove (manual 2.7.1.3 `own_rules`, D121), one by one;
             asked only after `firewall` is allowed.
    Inputs:  v — vars (security.firewall, default True; firewall_rules reads the rest); config_dir — the install's
             config folder.
    Returns: list of str ("ufw: remove <rule as ufw shows it> (the host's own)"); [] when there are none, or with
             security.firewall false.
    Fails:   errors of firewall_rules and host_own_rules.
    Feeds:   consent/plan_host_changes."""
    if not (v.get("security") or {}).get("firewall", True):
        return []
    rules = firewall_rules(v, config_dir)
    planned = ([("ssh", f"{c}@{p}") for c in rules["ssh"] for p in ssh_ports()] + [("ntp", c) for c in rules["ntp"]]
               + [("dhcp", i) for i in rules["dhcp"]] + [("ad", r) for r in rules["ad"]])
    return [f"ufw: remove `{r}` (the host's own)" for r in host_own_rules(config_dir, planned)]
