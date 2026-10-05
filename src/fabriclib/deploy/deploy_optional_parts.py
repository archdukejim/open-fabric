import shutil

from fabriclib.common.service_user import service_user
from fabriclib.consent.allowed_to_change import allowed_to_change
from fabriclib.consent.plan_time import plan_time
from fabriclib.dhcp.deploy_kea import deploy_kea
from fabriclib.dns_filter.deploy_adguard import deploy_adguard
from fabriclib.logs.deploy_fluentbit import deploy_fluentbit
from fabriclib.ntp.deploy_chrony import deploy_chrony
from fabriclib.radius.deploy_freeradius import deploy_freeradius
from fabriclib.samba.deploy_samba import deploy_samba


def deploy_optional_parts(paths, final_vars, secrets, jinja_env, links):
    """Purpose: the parts with a deploy step of their own: Fluent Bit, the DNS filter, time (chrony), Kea,
             FreeRADIUS and the Windows domain — each only when it is on (chrony whenever it is installed and the
             `time` host change is approved — manual 2.7.1; an install set up before consent existed keeps
             converging).
    Inputs:  paths — deploy_paths() (federation, config); final_vars — rendered settings; secrets; jinja_env; links —
             dns_links() (the zones AdGuard forwards to BIND).
    Returns: {"restart": set of units to restart, "nginx": True if nginx's sign-in snippet for AdGuard changed}.
    Fails:   whatever the parts' deploy functions raise (ValidationError, OSError, CalledProcessError).
    Feeds:   apply_deployment."""
    restart, nginx = set(), False
    # Fluent Bit (optional): its config, destination CAs, credentials, disk buffer
    if final_vars.get("install_fluentbit") and deploy_fluentbit(final_vars, secrets, jinja_env):
        restart.add("fluentbit")
    # DNS filter (manual 2.4.1): AdGuard's config merged with what it has, oauth2-proxy's, nginx's snippet
    if final_vars.get("install_adguard"):
        adg = deploy_adguard(final_vars, secrets, links, jinja_env)
        if adg["adguard"]:
            restart.add("adguard")
        if adg["oauth2proxy"]:
            restart.add("adguard-auth")
        nginx = adg["nginx"]
    # Time (manual 2.5.1): chrony on the host, the upstream site first; installed by setup's host step
    if shutil.which("chronyd"):
        if not allowed_to_change(paths["config"], "time", plan_time(), unasked_install=True):
            print("  time: chrony left as it is (the `time` host change is not approved; "
                  "`sudo fabricctl setup --approve time` allows it)")
        elif deploy_chrony(final_vars, paths["federation"], jinja_env, config_dir=paths["config"]):
            print("  time: chrony configuration updated")
    # Kea (optional): its configs (leases are kept across restarts) and the DHCP subzone, created once
    if final_vars.get("install_kea") and deploy_kea(final_vars, secrets, jinja_env, *service_user(final_vars, "bind")):
        restart.add("kea")
    # FreeRADIUS (optional): config with the client secrets, fabric's policy code, CA bundle
    if final_vars.get("install_freeradius") and deploy_freeradius(final_vars, secrets, jinja_env):
        restart.add("freeradius")
    # the directory (Samba AD, every install): the Administrator's password file (read only when provisioning),
    # the converge code, its resolver (a change restarts it)
    if deploy_samba(final_vars, secrets, jinja_env)["restart"]:
        restart.add("samba")
    return {"restart": restart, "nginx": nginx}
