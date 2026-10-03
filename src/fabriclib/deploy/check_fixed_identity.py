import os

from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.errors import ValidationError
from fabriclib.federation.common.site_name_problem import site_name_problem
from fabriclib.federation.constants import BASE_DN_RE

MARKERS = (("site_name", ".site-name"), ("org_domain", ".org-domain"), ("ldap_base_dn", ".ldap-base-dn"))


def check_fixed_identity(final_vars, config_dir):
    """Purpose: the settings that name the directory stay what they were at install: site_name (this site's part),
             org_domain and ldap_base_dn (the organisation's). Recorded on the first deploy.
    Inputs:  final_vars — rendered settings; config_dir — <fabric>/config (holds .site-name, .org-domain,
             .ldap-base-dn).
    Returns: None; a missing marker is written with the current value.
    Fails:   ValidationError when site_name is not one host-name label or names an organisation OU, ldap_base_dn is
             not dc=… or o=… followed by dc=… parts, or a value differs from its marker.
    Feeds:   apply_deployment (before anything is rendered or installed)."""
    org_ous = [ou.get("name") for ou in final_vars.get("ldap_organizational_units") or [] if not ou.get("parent")]
    problem = site_name_problem(final_vars.get("site_name", ""), org_ous)
    if problem:
        raise ValidationError(f"site_name: {problem}")
    if not BASE_DN_RE.match(str(final_vars.get("ldap_base_dn", ""))):
        raise ValidationError(f"ldap_base_dn '{final_vars.get('ldap_base_dn')}' is not dc=… or o=… followed by dc=… "
                              "parts")
    for key, name in MARKERS:
        marker = os.path.join(config_dir, name)
        if os.path.exists(marker):
            recorded = open(marker).read().strip()
            if recorded and recorded != final_vars.get(key):
                raise ValidationError(f"{key} is '{recorded}' on this install and cannot change "
                                      f"(asked: '{final_vars.get(key)}'); set {key}: {recorded}")
        else:
            ensure_dir(os.path.dirname(marker))
            with open(marker, "w") as f:
                f.write(str(final_vars.get(key, "")) + "\n")
