def plan_services():
    """Purpose: fabric's own units on the host (design host-consent.md §2 `services`), asked once as a kind: they
             follow from the services the admin turns on, so a new fabric unit does not ask again.
    Inputs:  none.
    Returns: list of str (fixed wording, so an approval stays valid across releases).
    Fails:   never.
    Feeds:   consent/plan_host_changes, deploy/apply_deployment (systemd units), setup/deploy_config."""
    return ["systemd: fabric's own units in /etc/systemd/system — fabric.target, one unit per fabric service, "
            "fabric-agent, fabric-* timers (enabled and started by setup)"]
