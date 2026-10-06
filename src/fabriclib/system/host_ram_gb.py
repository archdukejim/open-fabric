def host_ram_gb():
    """Purpose: this host's memory in GB, rounded (a 4 GB board reports a little less: 3.88 GiB on the Pi).
    Inputs:  none (/proc/meminfo).
    Returns: int, or 0 when it cannot be read.
    Fails:   never.
    Feeds:   setup/ask_ram (setup's question), deploy/render_vars (an install from before the question)."""
    try:
        with open("/proc/meminfo") as f:
            kb = next(int(line.split()[1]) for line in f if line.startswith("MemTotal:"))
        return round(kb / 1024 / 1024)
    except (OSError, StopIteration, ValueError):
        return 0
