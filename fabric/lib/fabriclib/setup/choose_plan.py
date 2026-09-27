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
        print("  ✓ Create an internal CA (Step-CA) and TLS certificates for every service")

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
            show()
