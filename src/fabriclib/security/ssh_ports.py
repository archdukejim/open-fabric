import subprocess

DEFAULT = 22


def ssh_ports():
    """Purpose: the ports this host's SSH daemon listens on, so the firewall opens those and not a guessed 22 (an
             sshd on another port would otherwise be shut out by fabric's deny-incoming default).
    Inputs:  none (runs `sshd -T`, which prints the daemon's effective settings; needs root).
    Returns: sorted list of int; [22] when there is no sshd or it cannot say.
    Fails:   never.
    Feeds:   setup/configure_firewall, consent/plan_firewall."""
    try:
        res = subprocess.run(["sshd", "-T"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return [DEFAULT]
    ports = sorted({int(line.split()[1]) for line in res.stdout.splitlines()
                    if line.startswith("port ") and line.split()[1].isdigit()})
    return ports or [DEFAULT]
