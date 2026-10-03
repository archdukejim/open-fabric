from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.setup.renew_service_certs import renew_service_certs
from fabriclib.system.apply_changes import apply_changes


def set_federation_endpoint(ctx, actor, on, source="cli"):
    """Purpose: turn the federation endpoint (federation.<domain>, sites join through it) on or off and apply.
    Inputs:  ctx — SetupContext of the install (for its certificates); actor — str (audit); on — bool;
             source — default "cli".
    Returns: (ok: bool, output: str) from apply_changes; (True, "already on/off") when nothing changes.
    Fails:   OSError / yaml errors from the vars file; as renew_service_certs (SetupError, ValidationError,
             CalledProcessError) when turning on; subprocess.TimeoutExpired from apply_changes.
    Feeds:   run_federation_command (enable, disable).
    Notes:   turning on issues the endpoint's certificate before the apply, so nginx never loads the vhost
             without it. Turning off stops new joins only: sites that joined stay. Audited as
             FED_ENDPOINT_ON / FED_ENDPOINT_OFF."""
    with vars_lock():
        data = load_vars()
        if bool(data.get("federation_endpoint")) == bool(on):
            return True, f"the federation endpoint is already {'on' if on else 'off'}"
        data["federation_endpoint"] = bool(on)
        save_vars(data)
    write_audit(actor, "FED_ENDPOINT_ON" if on else "FED_ENDPOINT_OFF", f"host={data.get('hostname_federation')}",
                source)
    if on:
        renew_service_certs(ctx)
    return apply_changes(actor, source)
