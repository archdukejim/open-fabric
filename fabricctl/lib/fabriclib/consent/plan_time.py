import shutil


def plan_time():
    """Purpose: what fabric changes in the host's time service (design host-consent.md §2 `time`, ntp.md), asked
             once as a kind: the sources and served networks follow fabric's own NTP settings.
    Inputs:  none (looks for chronyd).
    Returns: list of str; [] without chrony (nothing to configure).
    Fails:   never.
    Feeds:   consent/plan_host_changes, deploy/deploy_optional_parts (deploy_chrony)."""
    if not shutil.which("chronyd"):
        return []
    return ["chrony: fabric writes /etc/chrony/chrony.conf and /etc/default/chrony (time sources and the networks "
            "it serves follow fabric's NTP settings) and limits chrony-wait to 90 s; systemd-timesyncd is disabled"]
