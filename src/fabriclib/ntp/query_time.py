import ipaddress
import re
import subprocess

WRONG_BY = re.compile(r"System clock wrong by (-?[0-9.]+) seconds")


def query_time(address, timeout=10):
    """Purpose: how far this host's clock is from another NTP server, without changing anything (manual 1.13.1.4: a site
                compares itself with its upstream site).
    Inputs:  address — the server's IP address (str); timeout — seconds to wait.
    Returns: the offset in seconds (float, signed: positive when this clock is behind), or None when the server
             did not answer in time.
    Fails:   ValueError when address is not an IP address (never passed to a command line otherwise).
    Feeds:   verify_install (doctor at a federated site); tests/ntp/run.py.
    Notes:   `chronyd -Q` with its own directives only (no config file, no command port, its own pid file), so it
             runs next to the chrony service."""
    ip = str(ipaddress.ip_address(address))
    cmd = ["chronyd", "-Q", "-t", str(int(timeout)), "-f", "/dev/null", "cmdport 0",
           "pidfile /run/chrony/fabric-query.pid", f"server {ip} iburst maxsamples 4"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = WRONG_BY.search(res.stdout + res.stderr)
    return float(m.group(1)) if m else None
