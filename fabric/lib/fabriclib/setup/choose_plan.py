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
    ("install_ldap", True, "389 Directory Server (LDAP for hosts and Keycloak)", "no central user directory"),
    ("install_keycloak", True, "Keycloak SSO (+ Postgres), required by the web UI", "no SSO and no web UI"),
    ("install_webui", True, "Fabric web UI at https://mgr.<domain> (mTLS client certificate + Keycloak login + TOTP)",
     "manage with fabricctl only"),
]


def _ask_log_forwarding(ctx):
    """Optional (off by default): Fluent Bit forwarding every log to syslog
    and/or Elasticsearch/OpenSearch (design D20)."""
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


def _get(data, dotted, default):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _set(data, dotted, value):
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def choose_plan(ctx):
    """Show what setup will do (every default is the hardened choice), then
    Proceed / Advanced / Quit. Advanced walks each item and states the cost
    of relaxing it. Choices are written into ctx.vars (and so into
    fabric.yaml), so a --file can set all of them non-interactively."""
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
        if ctx.vars.get("install_fluentbit"):
            print(f"  ✓ Optional: forward all logs with Fluent Bit to {', '.join(dests) or '(no destination yet)'}")
        else:
            print("  · Optional, off: forward all logs to syslog / Elasticsearch (Fluent Bit) — choose it in Advanced")

    # Record the effective value of every item, so what was shown is what
    # gets rendered (template defaults differ, e.g. install_keycloak).
    for key, default, _, _ in PLAN:
        _set(ctx.vars, key, bool(_get(ctx.vars, key, default)))
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
            _ask_log_forwarding(ctx)
            show()
