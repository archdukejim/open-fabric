import os
import platform
import shutil
import subprocess

from fabriclib.common.console import ok, warn
from fabriclib.setup.errors import SetupError

SUPPORTED_ARCH = {"x86_64": "amd64", "aarch64": "arm64"}
PUBLISHED_PORTS = (53, 80, 443, 389, 636, 853)
MIN_RAM_GB_WITH_KEYCLOAK = 3


def _os_release():
    """Purpose: parse /etc/os-release.
    Inputs:  none (reads /etc/os-release).
    Returns: dict of KEY -> value with quotes stripped; {} when the file is missing.
    Fails:   never on a missing file; OSError for other read errors.
    Feeds:   run."""
    info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                info[k] = v.strip('"')
    except FileNotFoundError:
        pass
    return info


def _mem_gb():
    """Purpose: total RAM in GiB.
    Inputs:  none (reads /proc/meminfo).
    Returns: MemTotal as float GiB; 0.0 if the line is absent.
    Fails:   FileNotFoundError without /proc/meminfo.
    Feeds:   run."""
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 1024 / 1024
    return 0.0


def _foreign_listeners():
    """Purpose: processes other than Docker listening on fabric's published ports (PUBLISHED_PORTS).
    Inputs:  none (runs `ss -H -ltnup`).
    Returns: list of "<addr:port> <process>" strings; systemd-resolved's loopback stub (127.0.0.53/54) and
             docker-proxy are ignored.
    Fails:   FileNotFoundError if `ss` is missing; a failing ss yields [].
    Feeds:   run (warnings only)."""
    res = subprocess.run(["ss", "-H", "-ltnup"], capture_output=True, text=True)
    found = []
    for line in res.stdout.splitlines():
        cols = line.split()
        if len(cols) < 5:
            continue
        addr = cols[4]
        port = addr.rsplit(":", 1)[-1]
        if port.isdigit() and int(port) in PUBLISHED_PORTS and "docker-proxy" not in line:
            if addr.startswith("127.0.0.53") or addr.startswith("127.0.0.54"):
                continue  # systemd-resolved stub: loopback only, no conflict
            proc = line.split("users:", 1)[1] if "users:" in line else "?"
            found.append(f"{addr} {proc}")
    return found


def run(ctx):
    """Purpose: refuse to install on a host that cannot run fabric correctly.
    Inputs:  ctx — SetupContext: vars.install_keycloak (default True; RAM check), offline (Docker must exist).
             Reads euid, platform, /etc/os-release, /proc/meminfo, /sys/fs/cgroup/cgroup.controllers, ss.
    Returns: None; prints what passed. Nothing on the host is changed. An untested OS and ports in use by
             other programs are warnings only.
    Fails:   SetupError when not root; SetupError listing every problem: unsupported architecture (not
             amd64/arm64), under MIN_RAM_GB_WITH_KEYCLOAK (less 0.3) with Keycloak, no cgroup v2 memory
             controller, offline without Docker.
    Feeds:   setup step `preflight`, run by run_setup via STEPS."""
    problems = []
    if os.geteuid() != 0:
        raise SetupError("Run as root: sudo fabricctl setup")

    arch = platform.machine()
    if arch not in SUPPORTED_ARCH:
        problems.append(f"unsupported architecture {arch} (need amd64 or arm64)")
    else:
        ok(f"architecture {SUPPORTED_ARCH[arch]}")

    rel = _os_release()
    if rel.get("ID") not in ("ubuntu", "debian"):
        warn(f"untested OS {rel.get('PRETTY_NAME', '?')} (reference: Ubuntu 24.04)")
    else:
        ok(rel.get("PRETTY_NAME", rel.get("ID")))

    mem = _mem_gb()
    want_kc = ctx.vars.get("install_keycloak", True)
    if want_kc and mem < MIN_RAM_GB_WITH_KEYCLOAK - 0.3:
        problems.append(f"{mem:.1f} GB RAM; Keycloak needs at least {MIN_RAM_GB_WITH_KEYCLOAK} GB")
    else:
        ok(f"{mem:.1f} GB RAM")

    try:
        with open("/sys/fs/cgroup/cgroup.controllers") as f:
            controllers = f.read().split()
    except FileNotFoundError:
        controllers = []
    if "memory" not in controllers:
        problems.append(
            "the cgroup v2 memory controller is not enabled, so Docker would silently ignore every "
            "memory limit. On a Raspberry Pi add 'cgroup_enable=memory' to the kernel command line "
            "(/boot/firmware/cmdline.txt) and reboot")
    else:
        ok("cgroup v2 memory controller enabled")

    if ctx.offline and not shutil.which("docker"):
        problems.append("offline install but Docker is not installed")

    for listener in _foreign_listeners():
        warn(f"port in use by another program: {listener}")

    if problems:
        raise SetupError("preflight failed:\n    - " + "\n    - ".join(problems))
