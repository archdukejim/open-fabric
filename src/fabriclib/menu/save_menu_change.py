import os

from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def menu_actor():
    """Purpose: the name recorded as the acting user for changes made in the vars editor.
    Inputs:  none; env SUDO_USER, then USER.
    Returns: str — SUDO_USER, else USER, else "root".
    Fails:   never.
    Feeds:   save_menu_change, edit_dns_zone (add_record / remove_record)."""
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"


def save_menu_change(path, data, key, old, new, action="MODIFIED"):
    """Purpose: save the editor's working copy and record the change in fabric's audit log.
    Inputs:  path — the file (vars.yaml or link-vars.yaml); data — the mapping written; key, old, new — what changed
             (shown as text); action — MODIFIED, ADDED or DELETED.
    Returns: None.
    Fails:   OSError writing the file; an audit-log OSError is ignored.
    Feeds:   every editor screen in fabriclib/menu.
    Notes:   under vars_lock, like every other vars edit (CLI, fabric-agent, web UI); empty strings are stored as
             null (save_vars)."""
    with vars_lock():
        save_vars(data, path)
    try:
        write_audit(menu_actor(), action, f"Key: {key} | Old: {old} | New: {new}")
    except OSError:
        pass
