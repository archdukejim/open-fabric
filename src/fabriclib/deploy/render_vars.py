from datetime import datetime, timezone

import yaml

from fabriclib.common.errors import ValidationError
from fabriclib.system.host_ram_gb import host_ram_gb

MIN_RAM_GB = 4                      # D31: a Raspberry Pi with 4 GB is the smallest host


def render_vars(jinja_env, secrets, custom_vars):
    """Purpose: the full settings: vars.yaml.j2 rendered over the admin's vars and fabric's secrets.
    Inputs:  jinja_env — fabric's Jinja environment; secrets — dict; custom_vars — the admin's vars (already merged
             by merge_tsig_keys / merge_radius_clients).
    Returns: (final_vars — the rendered settings, context — secrets + custom_vars + render_date: the start of what
             every other template renders with; the caller adds final_vars once they are checked).
    Fails:   ValidationError when vars.yaml.j2 does not render, or host_ram_capacity — the admin's, else this host's
             measured memory — is under 4 GB (D31; every container's memory limit follows from it, manual 1.3.4.2).
    Feeds:   apply_deployment."""
    context = {**secrets, **custom_vars, "host_ram_detected": host_ram_gb(),
               "render_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    try:
        final_vars = yaml.safe_load(jinja_env.get_template("vars.yaml.j2").render(**context)) or {}
    except Exception as e:                  # a template error of any kind: say which file
        raise ValidationError(f"vars.yaml.j2 did not render: {e}")
    ram = int(final_vars.get("host_ram_capacity") or 0)
    if ram < MIN_RAM_GB:
        raise ValidationError(f"host_ram_capacity is {ram} GB: fabric needs at least {MIN_RAM_GB} GB (D31). Set it to "
                              "this host's memory in GB, or leave it unset for setup to measure it.")
    return final_vars, context
