import os
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.deploy.compose_builds import compose_builds
from fabriclib.dns.install_zone_file import install_zone_file
from fabriclib.dns.reload_zone import reload_zone
from fabriclib.dns.rndc import rndc
from fabriclib.federation.configure_directory_links import configure_directory_links
from fabriclib.ldap.people_written_here import people_written_here
from fabriclib.ldap.seed_directory import seed_directory
from fabriclib.samba.converge_domain import converge_domain

TIMEOUT = {"keycloak": 90, "postgres": 60, "samba": 300}   # seconds per restart (others 30); the DC provisions once


def _quiet(cmd, what, timeout, capture=False):
    """Purpose: run a systemctl or docker command where a timeout is reported, not fatal.
    Inputs:  cmd — argument list; what — text for the message; timeout — seconds; capture — keep the output
             (else it goes to the console, as systemctl's own errors should).
    Returns: the CompletedProcess, or None after printing "<what> timed out".
    Fails:   never for a timeout; FileNotFoundError without the command.
    Feeds:   restart_changed."""
    try:
        return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"{what} timed out")
        return None


def _enabled(unit):
    """Purpose: whether a systemd unit is enabled (installed for boot).
    Inputs:  unit — name.
    Returns: bool.
    Fails:   FileNotFoundError without systemctl.
    Feeds:   restart_changed."""
    return subprocess.run(["systemctl", "is-enabled", "--quiet", unit]).returncode == 0


def restart_changed(paths, final_vars, secrets, state, bind_ids):
    """Purpose: the end of an apply on a running install: build changed images, restart what changed, reload BIND's
             configuration and zones and nginx live, converge the Windows domain, re-seed 389-DS, and restart
             fabric-agent, the federation endpoint and the web UI last without blocking.
    Inputs:  paths — deploy_paths() (base, target, federation); final_vars — rendered settings (federation_endpoint,
             install_ldap, ldap_base_dn, ldap_local_dn, install_samba and what converge_domain reads); secrets —
             fabric's secrets (the directory links); state — what the install steps found (see finish_without_start,
             plus ldap_seed); bind_ids — the bind user's ids.
    Returns: the set of units restarted (fabric-web included when it was queued).
    Fails:   ValidationError when BIND refuses `rndc reconfig` (a silent failure would leave a removed TSIG key
             working). Timeouts of systemctl/docker and a domain that cannot be converged are reported, not raised.
    Feeds:   apply_deployment (start_services=True: `fabricctl --apply`, the web UI's Apply).
    Notes:   BIND down or about to restart reads its zone files on start, so they are installed first. The web UI is
             restarted last with --no-block: this apply may have come from it. No --pull on image builds."""
    restart = set(state["restart"])
    if state["daemon_reload"]:
        print("Reloading systemd daemon...")
        _quiet(["systemctl", "daemon-reload"], "systemctl daemon-reload", 15)
    res = _quiet(["docker", "ps", "--format", "{{.Names}}"], "docker ps", 15, capture=True)
    running = res.stdout.split("\n") if res else []

    bind9_live = "bind9" in running and "bind9" not in restart
    if not bind9_live:
        for zone, src, dst in state["zones"]:
            install_zone_file(src, dst, *bind_ids)
    restart_webui = "fabric-web" in restart or state["webui"]
    restart.discard("fabric-web")
    for folder in sorted(state["rebuild"]):
        compose = os.path.join(paths["base"], folder, "docker-compose.yml")
        verb = "build" if compose_builds(compose) else "pull"     # fabric's published images are pulled
        print(f"{'Rebuilding' if verb == 'build' else 'Pulling'} {folder} image...")
        subprocess.run(["docker", "compose", "-f", compose, verb], timeout=1200)
    for svc in restart:
        print(f"Restarting {svc} due to configuration changes...")
        _quiet(["systemctl", "restart", svc], f"Restart of {svc}", TIMEOUT.get(svc, 30))

    print("Reloading active services...")
    if bind9_live:
        if state["bind9_config"]:
            print("Reloading BIND9 configuration...")
            # keys and update-policy grants (TSIG) take effect here; generous timeout: reconfig is slow on a loaded Pi
            res = rndc(["reconfig"], timeout=90)
            if res is None or res.returncode != 0:
                raise ValidationError("BIND9 did not accept the new configuration "
                                      f"({(res.stderr or res.stdout).strip() if res else 'timeout'}); "
                                      "check `docker logs bind9`.")
        for zone, src, dst in state["zones"]:
            reload_zone(zone, src, dst, *bind_ids)
    if "nginx" in running and "nginx" not in restart and state["nginx"]:
        print("Reloading NGINX...")
        _quiet(["docker", "exec", "nginx", "nginx", "-s", "reload"], "Reloading NGINX", 15)
    if final_vars.get("install_samba") and ("samba" in running or "samba" in restart):
        try:                                      # idempotent: the domain as fabric wants it (manual 2.11.2.15)
            done = converge_domain(final_vars, paths["federation"])
            print("Windows domain: " + ("; ".join(done) if done else "as wanted"))
        except ValidationError as e:              # reported: the rest of the apply still has to happen
            print(f"Warning: {e}")
    org_here = people_written_here(paths["federation"])
    if state["ldap_seed"] and ("dirsrv" in running or "ldap" in restart):
        print("Applying 389-DS seed data...")
        try:
            print(seed_directory(None if org_here else (final_vars["ldap_base_dn"], final_vars["ldap_local_dn"])))
        except ValidationError as e:              # reported: the rest of the apply still has to happen
            print(f"Warning: {e}")
    if final_vars.get("install_ldap", True) and ("dirsrv" in running or "ldap" in restart):
        try:                                      # the federation's directory links: a site joined or was removed
            linked = configure_directory_links(final_vars, secrets, paths["federation"])
            if linked:
                print("Directory replication: " + ", ".join(linked))
        except (ValidationError, RuntimeError) as e:
            print(f"Warning: directory replication: {e}")
    if state["agent"] and _enabled("fabric-agent"):
        print("Restarting fabric-agent (queued)...")            # --no-block: this apply may run inside it
        subprocess.run(["systemctl", "restart", "--no-block", "fabric-agent"], timeout=15)
    if final_vars.get("federation_endpoint") and (state["federation_unit"] or subprocess.run(
            ["systemctl", "is-active", "--quiet", "fabric-federation"]).returncode != 0):
        print("Starting the federation endpoint...")
        subprocess.run(["systemctl", "enable", "fabric-federation"], capture_output=True, timeout=30)
        subprocess.run(["systemctl", "restart", "fabric-federation"], timeout=30)
    if restart_webui and _enabled("fabric-web"):
        print("Restarting webui (queued)...")
        subprocess.run(["systemctl", "restart", "--no-block", "fabric-web"], timeout=15)
        restart.add("fabric-web")
    print("Deployment complete.")
    return restart
