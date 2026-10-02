from datetime import datetime, timezone

import yaml

from fabriclib.common.errors import ValidationError


def render_vars(jinja_env, secrets, custom_vars):
    """Purpose: the full settings: vars.yaml.j2 rendered over the admin's vars and fabric's secrets.
    Inputs:  jinja_env — fabric's Jinja environment; secrets — dict; custom_vars — the admin's vars (already merged
             by merge_tsig_keys / merge_radius_clients).
    Returns: (final_vars — the rendered settings, context — secrets + custom_vars + render_date: the start of what
             every other template renders with; the caller adds final_vars once they are checked).
    Fails:   ValidationError when vars.yaml.j2 does not render, or host_ram_capacity is 1 or 2 (3 GB is the minimum
             for Keycloak and Postgres; 0 is unlimited).
    Feeds:   apply_deployment."""
    context = {**secrets, **custom_vars,
               "render_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    try:
        final_vars = yaml.safe_load(jinja_env.get_template("vars.yaml.j2").render(**context)) or {}
    except Exception as e:                  # a template error of any kind: say which file
        raise ValidationError(f"vars.yaml.j2 did not render: {e}")
    ram = int(final_vars.get("host_ram_capacity", 0))
    if 0 < ram < 3:
        raise ValidationError(f"host_ram_capacity is set to {ram}. The absolute minimum is 3GB to safely run Keycloak "
                              "and Postgres. Set it to 0 for unlimited, or >= 3.")
    return final_vars, context
