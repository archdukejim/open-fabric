from fabriclib.common.errors import ValidationError
from fabriclib.deploy.check_samba_settings import check_samba_settings
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp
from fabriclib.dns_filter.check_filter_settings import check_filter_settings
from fabriclib.keycloak.signin_levels import signin_level
from fabriclib.ntp.normalize_ntp import normalize_ntp


def check_settings(final_vars):
    """Purpose: the rendered settings that are checked before anything is rendered or installed.
    Inputs:  final_vars — rendered settings; its `dhcp` is replaced by the normalized one.
    Returns: None.
    Fails:   ValidationError from normalize_dhcp (DHCP subnets, pools, reservations, dhcp.ntp) or normalize_ntp
             (ntp_servers, ntp_serve, ntp_set_clock), from check_samba_settings (the Windows domain), for a
             dns_filter other than none, adguard or bind, from check_filter_settings (the BIND resolver's lists,
             rules and upstreams), or from signin_level (a second factor that is not a level).
    Feeds:   apply_deployment."""
    final_vars["dhcp"] = normalize_dhcp(final_vars)
    normalize_ntp(final_vars)
    if final_vars.get("dns_filter") not in ("none", "adguard", "bind"):
        raise ValidationError(f"dns_filter must be none, adguard or bind (got {final_vars.get('dns_filter')!r})")
    if final_vars.get("dns_filter") == "bind":
        check_filter_settings(final_vars)
    for key in ("signin_admin_second_factor", "signin_everyone_second_factor"):
        final_vars[key] = signin_level(final_vars.get(key))
    check_samba_settings(final_vars)
