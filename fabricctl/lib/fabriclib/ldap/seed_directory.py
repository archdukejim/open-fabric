import subprocess
import time

from fabriclib.common.errors import ValidationError
from fabriclib.common.wait_healthy import wait_healthy

# dscontainer only records DS_SUFFIX_NAME in .dsrc: the backends are created on first run — the organisation
# suffix (people, groups, device roles) and this site's part below it (its service accounts and devices)
BACKENDS = ('dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" '
            '|| dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot',
            'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_LOCAL_SUFFIX (" '
            '|| dsconf localhost backend create --suffix "$DS_LOCAL_SUFFIX" --be-name sitelocal '
            '--parent-suffix "$DS_SUFFIX_NAME"')


def seed_directory():
    """Purpose: seed 389-DS: create the two suffix backends on first run, apply /seed/*.ldif idempotently inside the
             container (seed.py) and restart the ldap service once when server configuration (cn=config) changed.
    Inputs:  none; needs the running dirsrv container with DS_SUFFIX_NAME and DS_LOCAL_SUFFIX set and the rendered
             seed files (deploy/install_dirsrv_seed copies them to <base>/dirsrv/seed, mounted at /seed).
    Returns: seed.py's output (str), with a restart notice when it asked for one.
    Fails:   ValidationError when dirsrv does not become healthy (before seeding or after the restart), the backends
             cannot be created after 12 tries 5 s apart (the healthcheck can pass a moment before LDAPI accepts
             connections), or seed.py fails (its output in the message).
    Feeds:   setup/start_services (setup), deploy/restart_changed (apply when seed files changed);
             tests/dirsrv/run.sh mirrors the same steps."""
    healthy, why = wait_healthy("dirsrv", timeout=300, interval=5)
    if not healthy:
        raise ValidationError(f"dirsrv did not become healthy ({why})")
    for attempt in range(12):
        if all(subprocess.run(["docker", "exec", "dirsrv", "sh", "-c", cmd], capture_output=True).returncode == 0
               for cmd in BACKENDS):
            break
        time.sleep(5)
    else:
        raise ValidationError("389-DS backend could not be created")
    res = subprocess.run(["docker", "exec", "dirsrv", "sh", "-c", "python3 /seed/seed.py /seed/*.ldif"],
                         capture_output=True, text=True)
    out = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0:
        raise ValidationError(f"389-DS seeding failed:\n{out}")
    if "RESTART_REQUIRED" in res.stdout.splitlines():
        out += "\n389-DS configuration changed — restarting ldap service..."
        subprocess.run(["systemctl", "restart", "ldap"], check=True)
        healthy, why = wait_healthy("dirsrv", timeout=300, interval=5)
        if not healthy:
            raise ValidationError(f"dirsrv did not become healthy after its restart ({why})")
    return out.strip()
