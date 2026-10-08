import shutil


def plan_time():
    """Purpose: what fabric changes in the host's time service (manual 2.7.1.3 `time`, manual 2.5.1), asked
             once as a kind: the sources and served networks follow fabric's own NTP settings.
    Inputs:  none (looks for chronyd).
    Returns: list of str; [] without chrony (nothing to configure).
    Fails:   never.
    Feeds:   consent/plan_host_changes, deploy/deploy_optional_parts (deploy_chrony)."""
    if not shutil.which("chronyd"):
        return []
    return ["chrony: fabric writes /etc/chrony/chrony.conf and /etc/default/chrony (time sources and the networks "
            "it serves follow fabric's NTP settings, and it signs Windows members' time through the domain "
            "controller's socket in /var/lib/samba/ntp_signd) and limits chrony-wait to 90 s; systemd-timesyncd is "
            "disabled"]
