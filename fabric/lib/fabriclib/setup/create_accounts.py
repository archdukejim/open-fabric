import grp
import pwd
import subprocess

from fabriclib.common.console import ok, warn


def _exists(db, name):
    return subprocess.run(["getent", db, name], capture_output=True).returncode == 0


def _ensure_group(name, gid):
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
    """System users/groups for every service (nologin, no home), with the
    uid/gid fabric expects so bind-mounted files have the right owner.
    An id already taken by a different account is reported, not changed."""
    for name, ids in (ctx.vars.get("service_users") or {}).items():
        uid, gid = int(ids["uid"]), int(ids["gid"])
        if uid == 0:
            continue
        _ensure_group(name, gid)
        _ensure_user(name, uid, gid)
        ok(f"{name} ({uid}:{gid})")
