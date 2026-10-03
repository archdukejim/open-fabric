import subprocess


def rndc(args, timeout=15):
    """Purpose: run an rndc command inside the bind9 container as the bind user.
    Inputs:  args — list of rndc arguments (e.g. ["freeze", zone]; zone names come from validated vars); timeout —
             seconds, default 15.
    Returns: the subprocess.CompletedProcess (not checked: callers read returncode/stdout/stderr), or None on a timeout.
    Fails:   never raises for a failed command; prints "rndc <args> timed out" and returns None on a timeout.
    Feeds:   reload_zone, deploy/install_zones_and_restart (freeze before a restart, `rndc reconfig`)."""
    try:
        return subprocess.run(["docker", "exec", "-u", "bind", "bind9", "rndc", *args],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"rndc {' '.join(args)} timed out")
        return None
