from fabriclib.common.write_audit import write_audit
from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets


def set_machine_enabled(v, actor, name, enabled, source="web", secrets=None, container="samba"):
    """Purpose: disable a machine of this site, or enable it again (manual 2.10.2.6): while disabled its logons and
             its PEAP sign-in are refused; its account stays.
    Inputs:  v — fabric vars (site_name); actor — str, for the audit; name — the machine's host name; enabled — bool;
             source — audit source; secrets — fabric's secrets (default: load_secrets()); container — the DC's
             container.
    Returns: {"name", "enabled", "changed"}.
    Fails:   ValidationError from run_op ("no such entry": not a machine of this site; the DC not reachable).
    Feeds:   agent route POST /v1/machines/<name>/enable|disable (machines:admin).
    Notes:   audited as MACHINE_ENABLE / MACHINE_DISABLE when it changed something."""
    done = run_op(v, secrets if secrets is not None else load_secrets(), "set_machine",
                  {"name": name, "enabled": bool(enabled)}, container)
    if done.get("changed"):
        write_audit(actor, "MACHINE_ENABLE" if enabled else "MACHINE_DISABLE", f"machine={name}", source)
    return done
