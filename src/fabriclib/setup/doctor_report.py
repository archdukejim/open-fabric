from fabriclib.common.errors import ValidationError
from fabriclib.setup.context import SetupContext
from fabriclib.setup.verify_install import checks


def doctor_report(deploy_base="/opt"):
    """Purpose: `fabricctl doctor`'s checks as data, for the web console's Overview (2.1.8.3, manual 1.8.1): the same
             end-to-end checks, each with its result.
    Inputs:  deploy_base — the install root (default /opt). Runs as root (fabric-agent).
    Returns: {"checks": [{"name", "ok", "detail"}], "failed": int}; OpenBao locked is one failed check (the others
             need its secrets).
    Fails:   KeyError for missing settings; OSError reading the CA; as verify_install.checks otherwise.
    Feeds:   agent job "doctor" (POST /v1/jobs/doctor)."""
    try:
        rows = checks(SetupContext(deploy_base=deploy_base).load_state())
    except ValidationError as e:              # OpenBao locked: fabric's secrets cannot be read
        rows = [("fabric's secrets readable (OpenBao unlocked)", False, str(e))]
    out = [{"name": name, "ok": bool(ok), "detail": detail} for name, ok, detail in rows]
    return {"checks": out, "failed": sum(not c["ok"] for c in out)}
