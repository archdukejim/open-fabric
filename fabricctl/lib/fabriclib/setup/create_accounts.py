import grp
import pwd
import subprocess

from fabriclib.common.console import ok, warn


def _exists(db, name):
    """Purpose: whether a user or group name exists in the name service.
    Inputs:  db — "passwd" or "group"; name — account name.
    Returns: True if `getent db name` exits 0.
    Fails:   FileNotFoundError without getent.
    Feeds:   _ensure_group, _ensure_user."""
    return subprocess.run(["getent", db, name], capture_output=True).returncode == 0


def _ensure_group(name, gid):
    """Purpose: create a system group with the expected gid, unless the gid or name is already in use.
    Inputs:  name — group name; gid — int (0: nothing to do, e.g. Keycloak's image convention).
    Returns: None; a clash (gid owned by another group, or name with another gid) is warned about, not changed.
    Fails:   CalledProcessError from groupadd.
    Feeds:   run."""
    if gid == 0:            # keycloak runs with gid 0 (image convention): nothing to create
        return
    try:
        owner = grp.getgrgid(gid).gr_name
        if owner != name:
            warn(f"gid {gid} belongs to group '{owner}', expected '{name}' (service_users in vars)")
    except KeyError:
        if _exists("group", name):
            warn(f"group '{name}' exists with a different gid than {gid}")
        else:
            subprocess.run(["groupadd", "--system", "-g", str(gid), name], check=True)


def _ensure_user(name, uid, gid):
    """Purpose: create a nologin system user without home with the expected uid/gid, unless taken.
    Inputs:  name — user name; uid, gid — ints.
    Returns: None; a clash (uid owned by another user, or name with another uid) is warned about, not changed.
    Fails:   CalledProcessError from useradd (e.g. the gid does not exist).
    Feeds:   run."""
    try:
        owner = pwd.getpwuid(uid).pw_name
        if owner != name:
            warn(f"uid {uid} belongs to user '{owner}', expected '{name}' (service_users in vars)")
    except KeyError:
        if _exists("passwd", name):
            warn(f"user '{name}' exists with a different uid than {uid}")
        else:
            subprocess.run(["useradd", "--system", "-u", str(uid), "-g", str(gid), "-M", "-d", "/nonexistent",
                            "-s", "/usr/sbin/nologin", name], check=True)


def run(ctx):
    """Purpose: system users and groups for every service with the uid/gid fabric expects, so bind-mounted
             files have the right owner.
    Inputs:  ctx — SetupContext: vars.service_users {name: {uid, gid}}; entries with uid 0 are skipped.
    Returns: None; accounts exist (nologin, no home). An id already taken by a different account is reported,
             not changed. Idempotent.
    Fails:   KeyError/ValueError for an entry without numeric uid/gid; CalledProcessError from groupadd/useradd.
    Feeds:   setup step `accounts`, run by run_setup via STEPS."""
    for name, ids in (ctx.vars.get("service_users") or {}).items():
        uid, gid = int(ids["uid"]), int(ids["gid"])
        if uid == 0:
            continue
        _ensure_group(name, gid)
        _ensure_user(name, uid, gid)
        ok(f"{name} ({uid}:{gid})")
