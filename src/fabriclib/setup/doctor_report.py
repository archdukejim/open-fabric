import json
import os
import subprocess
import sys

from fabriclib.common.errors import ValidationError


def _checks(deploy_base):
    """Purpose: doctor's checks, run here.
    Inputs:  deploy_base — the install root.
    Returns: {"checks": [{"name", "ok", "detail"}], "failed": int}; OpenBao locked is one failed check.
    Fails:   as verify_install.checks.
    Feeds:   doctor_report, this file's __main__."""
    from fabriclib.setup.context import SetupContext
    from fabriclib.setup.verify_install import checks
    try:
        rows = checks(SetupContext(deploy_base=deploy_base).load_state())
    except ValidationError as e:              # OpenBao locked: fabric's secrets cannot be read
        rows = [("fabric's secrets readable (OpenBao unlocked)", False, str(e))]
    out = [{"name": name, "ok": bool(ok), "detail": detail} for name, ok, detail in rows]
    return {"checks": out, "failed": sum(not c["ok"] for c in out)}


def doctor_report(deploy_base="/opt"):
    """Purpose: `fabricctl doctor`'s checks as data, for the web console's Overview (2.1.8.3, manual 1.8.4.2): the same
             end-to-end checks, each with its result, run as a transient systemd unit outside fabric-agent's sandbox
             (the agent may reach only localhost and fabric_net; doctor asks DNS and nginx at the host's LAN address as
             a client would, and a site's time from its upstream).
    Inputs:  deploy_base — the install root (default /opt). Runs as root (fabric-agent).
    Returns: {"checks": [{"name", "ok", "detail"}], "failed": int}.
    Fails:   ValidationError "doctor did not run: …" when systemd-run fails or its output is not the report.
    Feeds:   agent job "doctor" (POST /v1/jobs/doctor)."""
    lib = os.path.join(deploy_base, "fabric", "lib")
    res = subprocess.run(["systemd-run", "--wait", "--pipe", "--collect", "--quiet", f"--setenv=PYTHONPATH={lib}",
                          sys.executable, "-m", "fabriclib.setup.doctor_report", deploy_base],
                         capture_output=True, text=True, timeout=900)
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValidationError(f"doctor did not run: {(res.stderr or res.stdout).strip()[-300:]}")


if __name__ == "__main__":                    # the transient unit: the report as one JSON line
    print(json.dumps(_checks(sys.argv[1] if len(sys.argv) > 1 else "/opt")))
