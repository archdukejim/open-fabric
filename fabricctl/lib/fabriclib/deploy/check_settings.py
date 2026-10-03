from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp
from fabriclib.ntp.normalize_ntp import normalize_ntp


def check_settings(final_vars):
    """Purpose: the rendered settings that are checked before anything is rendered or installed.
    Inputs:  final_vars — rendered settings; its `dhcp` is replaced by the normalized one.
    Returns: None.
    Fails:   ValidationError from normalize_dhcp (DHCP subnets, pools, reservations, dhcp.ntp) or normalize_ntp
             (ntp_servers, ntp_serve, ntp_set_clock), or for a dns_filter other than none or adguard.
    Feeds:   apply_deployment."""
    final_vars["dhcp"] = normalize_dhcp(final_vars)
    normalize_ntp(final_vars)
    if final_vars.get("dns_filter") not in ("none", "adguard"):
        raise ValidationError(f"dns_filter must be none or adguard (got {final_vars.get('dns_filter')!r})")
