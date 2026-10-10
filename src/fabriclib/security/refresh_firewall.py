import os
import re
import shutil
import subprocess
import sys

from fabriclib.common.paths import LIB_DIR


def refresh_firewall():
    """Purpose: bring the host firewall in line with the settings after a DHCP change made from the console or
             `fabricctl dhcp` (manual 1.10.3.5): setup's firewall step, unattended, with the `ports` group approved —
             the change is the admin's yes to the rules it implies (67/udp on a served interface, NTP and the domain
             controller's ports for its subnets). The host's own rules and securing keep their recorded answers.
    Inputs:  none. Runs `cli.py setup --step firewall --non-interactive --approve ports` through systemd-run when it
             is there (fabric-agent's sandbox cannot change the firewall), else directly. As root.
    Returns: (ok: bool, output: str without colour codes).
    Fails:   subprocess.TimeoutExpired after 300 s; OSError if Python cannot be started.
    Feeds:   dhcp/run_dhcp_command, agent/post_dhcp."""
    cmd = [sys.executable, os.path.join(LIB_DIR, "fabriclib", "cli.py"), "setup", "--step", "firewall",
           "--non-interactive", "--approve", "ports"]
    if shutil.which("systemd-run"):
        cmd = ["systemd-run", "--wait", "--pipe", "--collect", "--quiet", *cmd]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env={**os.environ, "TERM": "dumb"})
    return res.returncode == 0, re.sub(r"\x1b\[[0-9;]*m", "", res.stdout + res.stderr)
