import subprocess

from fabriclib.common.errors import ValidationError

UNIT = "fabric-dns-lists.service"


def start_list_fetch():
    """Purpose: start the lists job now (manual 1.12.2.14): fabric-agent has no internet by design, so a list added in
             the web console, or Fetch now, is fetched by the job's own unit, which then applies it (refresh_lists).
             Returns at once; the job runs on.
    Inputs:  none.
    Returns: True.
    Fails:   ValidationError when systemd refuses to start it (the unit missing: the resolver is off).
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/fetch, and after POST /v1/dns-filter/lists)."""
    r = subprocess.run(["systemctl", "start", "--no-block", UNIT], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise ValidationError(f"the lists job could not start: {(r.stderr or r.stdout).strip()[-200:]}")
    return True
