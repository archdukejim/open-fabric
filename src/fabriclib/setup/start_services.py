import os
import subprocess
import time

from fabriclib.common.console import info, ok
from fabriclib.common.errors import ValidationError
from fabriclib.directory.ensure_default_device_roles import ensure_default_device_roles
from fabriclib.ldap.migrate_local_suffix import migrate_local_suffix
from fabriclib.federation.configure_directory_links import configure_directory_links
from fabriclib.ldap.ensure_posix_identities import ensure_posix_identities
from fabriclib.ldap.people_written_here import people_written_here
from fabriclib.ldap.seed_directory import seed_directory
from fabriclib.samba.converge_domain import converge_domain
from fabriclib.samba.write_bind_dlz import write_bind_dlz
from fabriclib.setup.errors import SetupError
from fabriclib.setup.retire_renamed_units import retire_renamed_units
from fabriclib.setup.start_unit import start_unit

# (systemd unit, container, enabled-if flag); order = start order
ORDER = [("bind9", "bind9", None), ("stepca", "step-ca", None), ("samba", "samba", None),
         ("ldap", "dirsrv", "install_ldap"),
         ("postgres", "postgres", "install_keycloak"), ("keycloak", "keycloak", "install_keycloak"),
         ("nginx", "nginx", None), ("fluentbit", "fluentbit", "install_fluentbit"),
         ("kea", "kea-dhcp4", "install_kea"), ("freeradius", "freeradius", "install_freeradius"),
         ("adguard", "adguardhome", "install_adguard"), ("adguard-auth", "oauth2-proxy-adguard", "install_adguard")]


def run(ctx):
    """Purpose: start the stack in dependency order (ORDER), converge the Windows domain, seed 389-DS, configure
             Keycloak, move an older
             directory to the split layout (migrate_local_suffix), then fabric-agent and the web UI, and activate
             fabric.target.
    Inputs:  ctx — SetupContext: vars install_ldap (default True), install_keycloak, install_webui,
             install_fluentbit, install_kea, install_freeradius, install_adguard, federation_endpoint;
             restart_services
             (units to restart);
             target_dir (lib/keycloak_bootstrap.py), vars_file, secrets_file.
    Returns: None. fabric.target enabled and started; renamed units retired; every enabled unit running and its
             container healthy; 389-DS seeded and default device roles present; Keycloak configured (up to 6
             tries, 15 s apart); devices and service accounts in the local suffix; fabric-agent and fabric-web
             running when the web UI is on; fabric-federation running when federation_endpoint is on.
    Fails:   SetupError when a container is not healthy (start_unit), the Windows domain cannot be converged,
             seeding fails or Keycloak configuration
             still fails after 6 tries; CalledProcessError from systemctl; ValidationError from
             ensure_default_device_roles or migrate_local_suffix (propagates).
    Feeds:   setup step `start`, run by run_setup via STEPS."""
    v, lib = ctx.vars, os.path.join(ctx.target_dir, "lib")
    # fabric.target groups every unit: systemctl start|stop|restart fabric.target
    subprocess.run(["systemctl", "enable", "fabric.target"], check=True, capture_output=True)
    for unit in retire_renamed_units():
        ok(f"{unit}: retired (renamed)")
    for unit, container, flag in ORDER:
        if flag and not v.get(flag, flag == "install_ldap"):
            continue
        info(f"{unit}…")
        ok(f"{unit}: {start_unit(unit, container, unit in ctx.restart_services)}")

    try:
        done = converge_domain(v, os.path.join(ctx.config_dir, "federation.yaml"), ctx.secrets)
    except ValidationError as e:
        raise SetupError(str(e))
    ok(f"directory {v['ad_domain']}: " + (f"{len(done)} change(s)" if done else "as wanted"))
    if write_bind_dlz(v):                         # the first provisioning: BIND now serves the AD zone
        ok(f"bind9: {start_unit('bind9', 'bind9', True)} (the AD zone through DLZ)")
    if people_written_here(os.path.join(ctx.config_dir, "federation.yaml")):    # the root site: fabric's defaults
        try:
            added = ensure_default_device_roles(v, ctx.secrets, ctx.path("fabric", "config", ".default-device-roles"))
        except ValidationError as e:
            raise SetupError(str(e))
        if added:
            ok("default device roles: " + ", ".join(added))

    if v.get("install_ldap", True):
        registry = os.path.join(ctx.config_dir, "federation.yaml")
        org_here = people_written_here(registry)       # else a federated site: the organisation is a copy
        try:
            out = seed_directory(None if org_here else (v["ldap_base_dn"], v["ldap_local_dn"]))
        except ValidationError as e:
            raise SetupError(str(e))
        ok("389-DS seeded (" + (out.splitlines() or ["?"])[-1] + ")")
        if org_here:
            posix = ensure_posix_identities(v)
            if posix["added"]:
                ok("POSIX identities: " + ", ".join(posix["added"]))
        try:                                            # the federation's directory links (M5)
            linked = configure_directory_links(v, ctx.secrets, registry)
        except (ValidationError, RuntimeError) as e:
            raise SetupError(f"directory replication: {e}")
        if linked:
            ok("directory replication: " + ", ".join(linked))

    if v.get("install_keycloak"):
        for attempt in range(6):
            res = subprocess.run(["python3", os.path.join(lib, "keycloak_bootstrap.py"),
                                  "--vars", ctx.vars_file, "--secrets", ctx.secrets_file],
                                 capture_output=True, text=True)
            if res.returncode == 0:
                break
            time.sleep(15)
        else:
            raise SetupError(f"Keycloak configuration failed:\n{res.stdout}{res.stderr}")
        ok("Keycloak configured (realm, LDAP federation"
           + (", web UI client, TOTP)" if v.get("install_webui") else ")"))

    if v.get("install_ldap", True):             # after Keycloak moved to its new bind account
        moved = migrate_local_suffix(v)
        if any(moved.values()):
            ok(f"directory moved to the local suffix {v['ldap_local_dn']}: {moved['devices']} device(s), "
               f"{moved['role_members']} role membership(s), {moved['accounts']} old service account(s) removed")

    if v.get("install_webui"):
        subprocess.run(["systemctl", "enable", "--now", "fabric-agent"], check=True, capture_output=True)
        if "fabric-agent" in ctx.restart_services:
            subprocess.run(["systemctl", "restart", "fabric-agent"], check=True)
        ok(f"fabric-agent: {'restarted' if 'fabric-agent' in ctx.restart_services else 'running'}")
        ok(f"fabric-web: {start_unit('fabric-web', 'fabric-web', 'fabric-web' in ctx.restart_services)}")

    if v.get("federation_endpoint"):
        subprocess.run(["systemctl", "enable", "--now", "fabric-federation"], check=True, capture_output=True)
        if "fabric-federation" in ctx.restart_services:
            subprocess.run(["systemctl", "restart", "fabric-federation"], check=True)
        ok(f"fabric-federation: {'restarted' if 'fabric-federation' in ctx.restart_services else 'running'}")

    # Everything is up: activate the target now (it is enabled for boot), so
    # `fabricctl stop|restart` / `systemctl ... fabric.target` reach every unit.
    subprocess.run(["systemctl", "start", "fabric.target"], check=True, capture_output=True)
    ok("fabric.target active (systemctl status fabric.target)")
