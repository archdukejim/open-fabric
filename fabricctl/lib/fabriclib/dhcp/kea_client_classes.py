from fabriclib.dhcp.kea_option_data import kea_option_data


def kea_client_classes(classes):
    """Purpose: Kea's client-classes list from dhcp.client_classes (as normalize_client_classes returns them).
    Inputs:  classes — list of {name, test, options, next_server, server_hostname, boot_file_name}, or None.
    Returns: list of Kea client-class dicts: name, test, option-data, and next-server / server-hostname /
             boot-file-name when set (network boot).
    Fails:   never.
    Feeds:   jinja_env global kea_client_classes (kea/kea-dhcp4.conf.j2)."""
    out = []
    for c in classes or []:
        entry = {"name": c["name"], "test": c["test"], "option-data": kea_option_data([], c.get("options"))}
        for key, kea in (("next_server", "next-server"), ("server_hostname", "server-hostname"),
                         ("boot_file_name", "boot-file-name")):
            if c.get(key):
                entry[kea] = c[key]
        out.append(entry)
    return out
