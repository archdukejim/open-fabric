import subprocess

CONTAINER = "bind9-resolver"


def resolver_rndc(args, timeout=30):
    """Purpose: run an rndc command in the BIND resolver's container (manual 1.12.2.4), with its own control key.
    Inputs:  args — list of rndc arguments (e.g. ["reload", zone]; zone names come from list_zone); timeout — seconds,
             default 30.
    Returns: the subprocess.CompletedProcess (callers read returncode, stdout, stderr), or None when the container is
             not running or the command timed out.
    Fails:   never raises.
    Feeds:   dns_filter/update_lists (reload a changed list), dns_filter/deploy_resolver (reconfig),
             dns_filter/show_filter_status."""
    try:
        return subprocess.run(["docker", "exec", CONTAINER, "rndc", "-k", "/etc/bind/rndc.key", *args],
                              capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
