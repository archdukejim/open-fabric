import json
import os
import subprocess

from fabriclib.common.errors import ValidationError

# Connects inside the dirsrv container as Directory Manager over LDAPI, with the container's own DS_DM_PASSWORD
# (never on argv); the caller's code then has `c` (the connection), `ldap` and `e` (os.environ).
_PRELUDE = r'''
import json, os, time, ldap, ldap.modlist
e = os.environ
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
'''


def run_in_directory(code, inputs, container="dirsrv", timeout=120):
    """Purpose: run a short Python program in the 389-DS container, bound as Directory Manager over its local
             socket, and return what it prints as JSON (the address plan's readers and writers).
    Inputs:  code — Python source using `c`, `ldap` and `e` (see _PRELUDE) that prints one JSON value last;
             inputs — {name: str} passed as environment variables F_<name> (never on argv); container — the
             dirsrv container (tests pass theirs); timeout — seconds.
    Returns: the JSON value the program printed last.
    Fails:   ValidationError when 389-DS is not running; RuntimeError with the container's message for anything
             else; subprocess.TimeoutExpired.
    Feeds:   federation/publish_site_networks, publish_address_plan, read_address_plan."""
    env = {**os.environ, **{f"F_{k}": str(val) for k, val in inputs.items()}}
    args = ["docker", "exec", "-i"]
    for k in inputs:
        args += ["-e", f"F_{k}"]
    res = subprocess.run(args + [container, "python3", "-"], input=_PRELUDE + code, env=env,
                         capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0 and ("No such container" in res.stderr or "is not running" in res.stderr):
        raise ValidationError("389-DS (dirsrv) is not running — `sudo fabricctl status`")
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"directory: {(res.stderr or res.stdout).strip()[-500:]}")
    return json.loads(res.stdout.strip().splitlines()[-1])
