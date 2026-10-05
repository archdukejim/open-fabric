import subprocess

from fabriclib.common.errors import ValidationError


def finish_join(v, secrets, container="samba"):
    """Purpose: after this site's DC joined the domain (manual 1.8.8.4, S8.2): delete the temporary join account at
             the root's DC (it would expire within the hour anyway); the caller then forgets it (secrets ad_join).
    Inputs:  v — this site's vars (ad_join_server: the root DC's address); secrets — fabric's secrets (ad_join:
             {user, password}); container — this site's DC (its join credentials file is mounted at
             /run/secrets/join.auth, never on a command line).
    Returns: str, what was done ("" when there was no join account).
    Fails:   ValidationError when the root's DC refuses (an account already gone counts as done).
    Feeds:   setup/start_services (after the first convergence of a site that joined)."""
    join = secrets.get("ad_join") or {}
    if not join.get("user"):
        return ""
    res = subprocess.run(["docker", "exec", container, "samba-tool", "user", "delete", join["user"],
                          "-H", f"ldap://{v['ad_join_server']}", "-A", "/run/secrets/join.auth"],
                         capture_output=True, text=True, timeout=120)
    if res.returncode != 0 and "Unable to find" not in res.stderr + res.stdout:
        raise ValidationError("the join account could not be deleted at the root: "
                              + ((res.stderr or res.stdout).strip().splitlines() or ["no answer"])[-1])
    return f"join account {join['user']} deleted"
