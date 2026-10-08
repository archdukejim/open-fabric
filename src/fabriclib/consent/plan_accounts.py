import grp
import os
import pwd

from fabriclib.setup.common.previous_accounts import PREVIOUS_ACCOUNTS
from fabriclib.setup.common.service_account_name import service_account_name
from fabriclib.setup.errors import SetupError


def _uid_owner(uid):
    """Purpose: the user name that has a uid, or None.
    Inputs: uid — int.
    Returns: str or None.
    Fails: never.
    Feeds:   plan_accounts."""
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return None


def _gid_owner(gid):
    """Purpose: the group name that has a gid, or None.
    Inputs: gid — int.
    Returns: str or None.
    Fails: never.
    Feeds:   plan_accounts."""
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return None


def _user_uid(name):
    """Purpose: a user's uid, or None.
    Inputs: name — str.
    Returns: int or None.
    Fails: never.
    Feeds: plan_accounts."""
    try:
        return pwd.getpwnam(name).pw_uid
    except KeyError:
        return None


def _group_gid(name):
    """Purpose: a group's gid, or None.
    Inputs: name — str.
    Returns: int or None.
    Fails: never.
    Feeds: plan_accounts."""
    try:
        return grp.getgrnam(name).gr_gid
    except KeyError:
        return None


def _fabric_dirs(deploy_base, jinja_dir):
    """Purpose: the folders whose files fabric's service accounts own: each service's folder under the deploy base
             (one per template folder with a compose file), the install itself and /etc/fabric.
    Inputs:  deploy_base — e.g. /opt; jinja_dir — fabric's template folder.
    Returns: the existing folders, sorted (list of str).
    Fails:   OSError listing jinja_dir.
    Feeds:   plan_accounts (moving files from an old account to its fabric-* one)."""
    dirs = [os.path.join(deploy_base, d) for d in os.listdir(jinja_dir)
            if os.path.exists(os.path.join(jinja_dir, d, "docker-compose.yml.j2"))]
    dirs += [os.path.join(deploy_base, "fabric"), "/etc/fabric"]
    return sorted(d for d in dirs if os.path.isdir(d))


def plan_accounts(v, deploy_base, jinja_dir):
    """Purpose: the service accounts setup creates, and the old ones it moves away from (manual 1.2.9.3 `accounts`, §5):
                one fabric-* user and group per service_users entry, in fabric's uid band.
    Inputs:  v — vars: service_users {key: {uid, gid[, name]}} (uid 0 entries are skipped; gid 0 — Keycloak's
             image convention — has no group of its own); deploy_base, jinja_dir — for _fabric_dirs.
    Returns: list of actions in order, each {"text": what the question shows, "do": "group"|"user"|"move"|"remove",
             + its fields}: groups and users to create; for an install that still has a previous account
             (PREVIOUS_ACCOUNTS, matched by name AND id, so only fabric's own), moving its files to the new
             account and removing it. [] when everything is in place.
    Fails:   SetupError when an id is taken by another account or a name has another id (the message names both:
             fabric never takes over someone else's account); OSError from _fabric_dirs.
    Feeds:   consent/plan_host_changes (the question), setup/create_accounts (the step does exactly these)."""
    actions, moves = [], []
    for key, ids in (v.get("service_users") or {}).items():
        uid, gid = int(ids["uid"]), int(ids["gid"])
        if uid == 0:
            continue
        name = service_account_name(key, ids)
        if gid:
            holder, has = _gid_owner(gid), _group_gid(name)
            if holder not in (None, name) or (has is not None and has != gid):
                raise SetupError(f"group id {gid} for {name} is taken by '{holder}' (or {name} has gid {has}): "
                                 f"choose another id with service_users.{key}.gid")
            if holder is None:
                actions.append({"do": "group", "name": name, "gid": gid, "text": f"create group {name} (gid {gid})"})
        holder, has = _uid_owner(uid), _user_uid(name)
        if holder not in (None, name) or (has is not None and has != uid):
            raise SetupError(f"user id {uid} for {name} is taken by '{holder}' (or {name} has uid {has}): "
                             f"choose another id with service_users.{key}.uid")
        if holder is None:
            actions.append({"do": "user", "name": name, "uid": uid, "gid": gid,
                            "text": f"create user {name} (uid {uid}, gid {gid}; no login, no home)"})
        old_name, old_uid, old_gid = PREVIOUS_ACCOUNTS.get(key, (None, None, None))
        if old_name and old_name != name and _user_uid(old_name) == old_uid and (old_uid, old_gid) != (uid, gid):
            moves.append((old_name, old_uid, old_gid, name, uid, gid))
    dirs = _fabric_dirs(deploy_base, jinja_dir) if moves else []
    for old_name, old_uid, old_gid, name, uid, gid in moves:
        group = old_gid and _group_gid(old_name) == old_gid
        actions.append({"do": "move", "uid": (old_uid, uid), "gid": (old_gid, gid) if group else None, "dirs": dirs,
                        "text": f"give {name} the files of the old account {old_name} ({old_uid}:{old_gid}) in "
                                + ", ".join(dirs)})
        actions.append({"do": "remove", "name": old_name, "group": bool(group),
                        "text": f"remove the old account {old_name} (uid {old_uid})"
                                + (f" and its group (gid {old_gid})" if group else "") + ", created by fabric"})
    return actions
