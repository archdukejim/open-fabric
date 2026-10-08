import subprocess

LOCAL_REFID = "7F7F0101"      # chrony's own clock ("local stratum …"): serving, but synchronised to nothing


def time_status():
    """Purpose: this host's time synchronisation as chrony reports it (manual 1.13.1.4).
    Inputs:  none (runs `chronyc -n -c tracking` over chrony's local socket).
    Returns: {"synced": bool, "source": str, "stratum": int, "offset": float seconds (absolute), "leap": str,
             "local": bool} — synced only with a real source (not chrony's own clock, not "Not synchronised");
             {"synced": False, "error": str} when chrony does not answer.
    Fails:   never (errors are reported in the result).
    Feeds:   verify_install (doctor), service status output; tests/ntp/run.py."""
    try:
        res = subprocess.run(["chronyc", "-n", "-c", "tracking"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"synced": False, "error": str(e)}
    fields = res.stdout.strip().split(",")
    if res.returncode != 0 or len(fields) < 14:
        return {"synced": False, "error": (res.stderr or res.stdout).strip() or "chronyc failed"}
    refid, name, leap = fields[0].upper(), fields[1], fields[13]
    try:
        stratum, offset = int(fields[2]), abs(float(fields[4]))
    except ValueError:
        return {"synced": False, "error": f"unexpected chronyc output: {res.stdout.strip()}"}
    local = refid == LOCAL_REFID
    synced = not local and refid != "00000000" and leap != "Not synchronised" and stratum < 16
    return {"synced": synced, "source": "this host's own clock" if local else name, "stratum": stratum,
            "offset": offset, "leap": leap, "local": local}
