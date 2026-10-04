def kea_image(env, v):
    """Purpose: the Kea image this host runs, for checking a Kea file before it is written: fabric's published image
             when the host uses it (manual 2.6.3.3), otherwise its local build.
    Inputs:  env — the Jinja environment of the deploy (jinja_env: its published_ref holds the rule); v — the vars.
    Returns: str image ref or name ("fabric/kea:local" when image_kea is unset).
    Fails:   jinja2 errors only if the environment lacks published_ref (not one made by jinja_env).
    Feeds:   dhcp/deploy_kea, dhcp/common/edit_dhcp (both pass it to check_kea_config)."""
    return env.from_string("{{ published_ref('kea') or image_kea | default('fabric/kea:local') }}").render(**v)
