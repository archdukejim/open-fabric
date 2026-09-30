def fabric_groups(v):
    """The directory groups that carry a fabric role bundle (the admins group
    and every ldap_groups entry with a `bundle`)."""
    return {v.get("webui_admin_group", "admins")} | {g["name"] for g in v.get("ldap_groups") or [] if g.get("bundle")}
