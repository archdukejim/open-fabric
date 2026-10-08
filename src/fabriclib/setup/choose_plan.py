from fabriclib.common.console import BOLD, NC, YELLOW, heading

# (settings key, default, what enabling it does, what relaxing it costs)
PLAN = [
    ("security.firewall", True,
     "Host firewall: only fabric's ports inbound, from the LAN only (also enforced for Docker-published ports)",
     "every published port (DNS, LDAP, HTTPS, ...) reachable from any network that can route to this host"),
    ("security.docker_daemon_hardening", True,
     "Harden the Docker daemon (no-new-privileges, no inter-container traffic on the default bridge, "
     "no userland proxy, live-restore, bounded logs)",
     "containers may gain privileges via setuid binaries; logs can fill the disk"),
    ("install_keycloak", True, "Keycloak SSO (+ Postgres), required by the web UI", "no SSO and no web UI"),
    ("install_webui", True, "Fabric web UI at https://mgr.<domain> (mTLS client certificate + Keycloak login + TOTP)",
     "manage with fabricctl only"),
]


def _ask_log_forwarding(ctx):
    """Purpose: Advanced plan question: forward all logs with Fluent Bit (off by default, design D20).
    Inputs:  ctx — SetupContext; reads and writes ctx.vars install_fluentbit and log_forwarding (syslog host/port,
             elastic url/user). Interactive (input()).
    Returns: None; ctx.vars updated. A syslog target without port uses 6514; the Elasticsearch password is set
             later with `fabricctl logs set-password elastic`.
    Fails:   EOFError from input() when stdin is closed.
    Feeds:   choose_plan (Advanced)."""
    on = bool(ctx.vars.get("install_fluentbit"))
    answer = input(f"\n  Optional: forward all logs (journal, audit logs) to syslog and/or Elasticsearch "
                   f"(Fluent Bit)? [{'Y/n' if on else 'y/N'}] ").strip().lower()
    on = answer.startswith("y") if answer else on
    ctx.vars["install_fluentbit"] = on
    if not on:
        return
    lf = dict(ctx.vars.get("log_forwarding") or {})
    sl = dict(lf.get("syslog") or {})
    target = input(f"    syslog server host[:port] over TLS (blank: none) [{sl.get('host', '')}] ").strip()
    if target:
        host, _, port = target.partition(":")
        sl.update(host=host, port=int(port) if port.isdigit() else 6514)
    es = dict(lf.get("elastic") or {})
    url = input(f"    Elasticsearch/OpenSearch URL, https://host:port (blank: none) [{es.get('url', '')}] ").strip()
    if url:
        es["url"] = url
        es["user"] = input(f"    its user [{es.get('user', 'fabric')}] ").strip() or es.get("user", "fabric")
        print("    set its password after setup: sudo fabricctl logs set-password elastic   (kept in OpenBao)")
    lf.update({k: val for k, val in (("syslog", sl), ("elastic", es)) if val})
    ctx.vars["log_forwarding"] = lf


def _ask_dhcp(ctx):
    """Purpose: Advanced plan question: serve DHCP with Kea (off by default), and its interface, subnet,
             pool and router.
    Inputs:  ctx — SetupContext; reads and writes ctx.vars install_kea and dhcp; defaults from lan_cidr,
             lan_gateway and detect_network(). Interactive.
    Returns: None; ctx.vars["dhcp"] = one interface and one subnet (existing reservations kept). The default
             pool is the top quarter of the subnet; empty when the subnet has 8 hosts or fewer.
    Fails:   ValueError from ipaddress when the subnet typed (or defaulted) is not a network; EOFError from
             input().
    Feeds:   choose_plan (Advanced)."""
    import ipaddress
    from fabriclib.setup.detect_network import detect_network
    on = bool(ctx.vars.get("install_kea"))
    answer = input(f"\n  Optional: serve DHCP on this LAN with Kea (hostnames in dhcp.<domain>)? "
                   f"[{'Y/n' if on else 'y/N'}] ").strip().lower()
    on = answer.startswith("y") if answer else on
    ctx.vars["install_kea"] = on
    if not on:
        return
    print(f"    {YELLOW}One DHCP server per LAN: switch off your router's DHCP before fabric's starts.{NC}")
    net = detect_network()
    d = dict(ctx.vars.get("dhcp") or {})
    cidr = (d.get("subnets") or [{}])[0].get("subnet") or ctx.vars.get("lan_cidr") or net.get("lan_cidr") or ""
    iface = input(f"    interface [{(d.get('interfaces') or [net.get('interface') or 'eth0'])[0]}] ").strip() \
        or (d.get("interfaces") or [net.get("interface") or "eth0"])[0]
    cidr = input(f"    subnet [{cidr}] ").strip() or cidr
    hosts = list(ipaddress.ip_network(cidr, strict=False).hosts())
    pool_default = f"{hosts[len(hosts) * 3 // 4]} - {hosts[-2]}" if len(hosts) > 8 else ""
    pool = input(f"    address pool [{pool_default}] ").strip() or pool_default
    router = input(f"    router [{ctx.vars.get('lan_gateway') or net.get('lan_gateway') or ''}] ").strip() \
        or ctx.vars.get("lan_gateway") or net.get("lan_gateway") or ""
    d.update(interfaces=[iface], subnets=[{"subnet": cidr, "pools": [pool], **({"routers": router} if router else {}),
                                          "reservations": (d.get("subnets") or [{}])[0].get("reservations") or []}])
    ctx.vars["dhcp"] = d


def _ask_radius(ctx):
    """Purpose: Advanced plan question: 802.1X with FreeRADIUS (off by default).
    Inputs:  ctx — SetupContext; reads ctx.vars install_freeradius. Interactive.
    Returns: None; ctx.vars["install_freeradius"] set (it asks the site's DC, part of every install). Switches are
             added later (`fabricctl radius add-client`).
    Fails:   EOFError from input().
    Feeds:   choose_plan (Advanced)."""
    on = bool(ctx.vars.get("install_freeradius"))
    answer = input(f"\n  Optional: 802.1X with FreeRADIUS (devices join by certificate or MAC, VLAN per role)? "
                   f"[{'Y/n' if on else 'y/N'}] ").strip().lower()
    on = answer.startswith("y") if answer else on
    ctx.vars["install_freeradius"] = on
    if on:
        print("    Add your switches and access points afterwards: sudo fabricctl radius add-client <name> <address>")


CLOUDFLARE = ["https://1.1.1.1/dns-query", "https://1.0.0.1/dns-query"]     # vars.yaml.j2's default (D112)


def _upstreams_text(ctx):
    """Purpose: how the plan names the DNS filter's internet upstreams.
    Inputs:  ctx — SetupContext; reads ctx.vars adguard_upstreams (None: the default).
    Returns: "Cloudflare (DNS-over-HTTPS)", "local DNS only" or the upstreams joined by ", ".
    Fails:   never.
    Feeds:   choose_plan, _ask_dns_filter."""
    ups = ctx.vars.get("adguard_upstreams")
    if ups is None or list(ups) == CLOUDFLARE:
        return "Cloudflare (DNS-over-HTTPS)"
    return ", ".join(ups) or "local DNS only"


def _ask_dns_filter(ctx):
    """Purpose: Advanced plan question: the DNS filter, AdGuard Home (on by default, D112), and where it sends
             internet lookups.
    Inputs:  ctx — SetupContext; reads ctx.vars dns_filter, adguard_upstreams. Interactive.
    Returns: None; ctx.vars["dns_filter"] set ("adguard" or "none"), and adguard_upstreams when typed (they only
             seed a first deploy: afterwards AdGuard's own page owns them).
    Fails:   EOFError from input().
    Feeds:   choose_plan (Advanced)."""
    on = ctx.vars.get("dns_filter", "adguard") == "adguard"
    answer = input(f"\n  DNS filter: AdGuard Home answers the network's DNS (ads, trackers and malware blocked)? "
                   f"[{'Y/n' if on else 'y/N'}] ").strip().lower()
    on = answer.startswith("y") if answer else on
    ctx.vars["dns_filter"] = "adguard" if on else "none"
    if not on:
        return
    ups = input(f"    internet lookups go to (comma-separated DoH/DoT/IP upstreams) [{_upstreams_text(ctx)}] ").strip()
    if ups:
        ctx.vars["adguard_upstreams"] = [u.strip() for u in ups.split(",") if u.strip()]


def _get(data, dotted, default):
    """Purpose: read a dotted key ("security.firewall") from nested dicts.
    Inputs:  data — dict; dotted — key path; default — value when any part is missing or not a dict.
    Returns: the value found, or default.
    Fails:   never.
    Feeds:   choose_plan."""
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _set(data, dotted, value):
    """Purpose: write a dotted key into nested dicts, creating intermediate dicts.
    Inputs:  data — dict (modified); dotted — key path; value — value to store.
    Returns: None.
    Fails:   TypeError/AttributeError if an intermediate key holds a non-dict value.
    Feeds:   choose_plan."""
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def choose_plan(ctx):
    """Purpose: show what setup will do (every default is the hardened choice), then Proceed / Advanced / Quit.
             Advanced walks each PLAN item, states the cost of relaxing it, and asks the DNS filter and the optional
             services.
    Inputs:  ctx — SetupContext: vars (PLAN keys, install_* flags, log_forwarding, dhcp, radius_clients,
             webui_admin_user), non_interactive, assume_yes. Interactive unless one of those two is set.
    Returns: None. Every PLAN item's effective value is written into ctx.vars (so what was shown is what gets
             rendered), and dns_filter (AdGuard on unless set to none, D112); install_webui is forced off when
             Keycloak is off. deploy_config saves ctx.vars to
             fabric.yaml, so a --file can set all of these non-interactively.
    Fails:   SystemExit("setup cancelled") on Quit; EOFError from input(); errors of the _ask_* helpers.
    Feeds:   run_setup main (full runs only, after collect_vars)."""
    def show():
        heading("fabricctl setup will:")
        for key, default, does, _ in PLAN:
            on = bool(_get(ctx.vars, key, default))
            mark = "✓" if on else f"{YELLOW}✗{NC}"
            print(f"  {mark} {does}" + ("" if on else f"  {YELLOW}(disabled: {key}){NC}"))
        print("  ✓ Run every service non-root with no capabilities and a read-only filesystem")
        print("  ✓ Create an internal CA (Step-CA) and TLS certificates for every service; trust it on this host")
        if _get(ctx.vars, "install_webui", True):
            print(f"  ✓ Create the first web UI admin '{ctx.vars.get('webui_admin_user')}' with a client certificate; "
                  "login kit in ~/fabric-admin")
        lf = ctx.vars.get("log_forwarding") or {}
        dests = [d for d in ((lf.get("syslog") or {}).get("host"), (lf.get("elastic") or {}).get("url")) if d]
        if ctx.vars.get("dns_filter", "adguard") == "adguard":
            print(f"  ✓ DNS filter: AdGuard Home answers DNS on port 53, internet lookups to {_upstreams_text(ctx)}, "
                  "AdGuard's DNS filter; its page https://adguard.<domain>")
        else:
            print("  · Optional, off: DNS filter (AdGuard Home) — choose it in Advanced")
        if ctx.vars.get("install_kea"):
            subnets = ", ".join(s.get("subnet", "?") for s in (ctx.vars.get("dhcp") or {}).get("subnets") or [])
            print(f"  ✓ Optional: DHCP with Kea 3.0 on {subnets or '(no subnet yet)'}; hostnames in dhcp.<domain>")
        else:
            print("  · Optional, off: DHCP with Kea (hostnames registered in DNS) — choose it in Advanced")
        if ctx.vars.get("install_freeradius"):
            n = len(ctx.vars.get("radius_clients") or [])
            print(f"  ✓ Optional: 802.1X with FreeRADIUS ({n} RADIUS client{'s' if n != 1 else ''})")
        else:
            print("  · Optional, off: 802.1X with FreeRADIUS — choose it in Advanced")
        if ctx.vars.get("install_fluentbit"):
            print(f"  ✓ Optional: forward all logs with Fluent Bit to {', '.join(dests) or '(no destination yet)'}")
        else:
            print("  · Optional, off: forward all logs to syslog / Elasticsearch (Fluent Bit) — choose it in Advanced")

    # Record the effective value of every item, so what was shown is what
    # gets rendered (template defaults differ, e.g. install_keycloak).
    for key, default, _, _ in PLAN:
        _set(ctx.vars, key, bool(_get(ctx.vars, key, default)))
    ctx.vars["dns_filter"] = str(ctx.vars.get("dns_filter") or "adguard").lower()
    show()
    if ctx.non_interactive or ctx.assume_yes:
        return
    while True:
        choice = input(f"\n  {BOLD}[P]roceed{NC}, [A]dvanced, or [Q]uit? ").strip().lower() or "p"
        if choice.startswith("q"):
            raise SystemExit("setup cancelled")
        if choice.startswith("p"):
            return
        if choice.startswith("a"):
            for key, default, does, cost in PLAN:
                on = bool(_get(ctx.vars, key, default))
                answer = input(f"\n  {does}\n    Keep {'enabled' if on else 'disabled'}? [Y/n] ").strip().lower()
                if answer.startswith("n"):
                    on = not on
                    if not on:
                        print(f"    {YELLOW}Relaxed: {cost}{NC}")
                _set(ctx.vars, key, on)
            if not _get(ctx.vars, "install_keycloak", True):
                _set(ctx.vars, "install_webui", False)
            _ask_dns_filter(ctx)
            _ask_dhcp(ctx)
            _ask_radius(ctx)
            _ask_log_forwarding(ctx)
            show()
