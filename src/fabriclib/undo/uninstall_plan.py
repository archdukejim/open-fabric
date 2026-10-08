from fabriclib.consent.groups import GROUPS
from fabriclib.undo.undo_group import UNDO

# what uninstall does with each kind of host change (manual 1.2.9.4, step 8)
REMOVED = {
    "services": "fabric's systemd units, fabric.target, /usr/local/bin/fabricctl and the vault unlock udev rule",
    "accounts": "the fabric-* service accounts and their groups",
}
KEPT = {
    "packages": "apt packages stay (docker.io, chrony, ufw, …): `sudo apt remove` the ones nothing else uses",
    "runtime": "Docker's daemon settings stay: undoing them restarts Docker, so it is never done by uninstall; "
               "run `sudo fabricctl setup --undo runtime` first to put them back",
}


# undone together with the host firewall (undo/undo_firewall, 2.1.2.13)
WITH_FIREWALL = {
    "ports": "the ufw rules opening fabric's ports are removed with the host firewall's",
    "own_rules": "the host's own ufw rules fabric removed are put back with the host firewall's undo",
}


def uninstall_plan():
    """Purpose: what `fabricctl uninstall` does with each kind of host change, shown before it asks (manual 1.2.9.4,
                step 8).
    Inputs:  none.
    Returns: list of (group title, "removed" | "undone" | "kept", what) in groups.GROUPS order.
    Fails:   never.
    Feeds:   setup/run_uninstall_command."""
    rows = []
    for group, meta in GROUPS.items():
        if group in REMOVED:
            rows.append((meta["title"], "removed", REMOVED[group]))
        elif group in KEPT:
            rows.append((meta["title"], "kept", KEPT[group]))
        elif group in WITH_FIREWALL:
            rows.append((meta["title"], "undone", WITH_FIREWALL[group]))
        else:
            rows.append((meta["title"], "undone", UNDO[group][0]))
    return rows
