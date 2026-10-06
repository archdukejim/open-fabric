from fabriclib.common.console import info
from fabriclib.setup.errors import SetupError
from fabriclib.system.host_ram_gb import host_ram_gb

MIN_RAM_GB = 4                      # D31: a Raspberry Pi with 4 GB is the smallest host


def _plan(gb):
    """Purpose: what fabric's largest containers may use at a size, as the compose files set it (manual 1.3.4.2).
    Inputs:  gb — int, host_ram_capacity.
    Returns: str, e.g. "Keycloak 2400 MB, the domain controller 1024 MB, Postgres 400 MB, BIND 256 MB".
    Fails:   never.
    Feeds:   ask_ram."""
    f = gb / 4
    return (f"Keycloak {int(1200 * f)} MB, the domain controller {int(512 * f)} MB, Postgres {int(200 * f)} MB, "
            f"BIND {int(128 * f)} MB")


def ask_ram(ctx, data):
    """Purpose: how much of this host fabric sizes itself for (D31, manual 1.3.4.2): setup measures the host's memory
             and asks, the measured amount the default; less restricts fabric, leaving the rest to other work on the
             host. Asked once: the answer is kept as host_ram_capacity (change it with `fabricctl edit` or a vars
             file).
    Inputs:  ctx — SetupContext (non_interactive); data — the settings so far (changed: host_ram_capacity).
    Returns: None.
    Fails:   SetupError when the host has less than 4 GB, or an unattended setup's host_ram_capacity is under 4 or
             more than the host has.
    Feeds:   collect_vars."""
    have = host_ram_gb()
    if have and have < MIN_RAM_GB:
        raise SetupError(f"this host has {have} GB of memory: fabric needs at least {MIN_RAM_GB} GB (D31)")
    set_ = int(data.get("host_ram_capacity") or 0)
    if set_:
        if set_ < MIN_RAM_GB or (have and set_ > have):
            raise SetupError(f"host_ram_capacity is {set_} GB: give {MIN_RAM_GB} to {have or 'the host'}'s GB")
        return
    if ctx.non_interactive or not have:
        data["host_ram_capacity"] = have or MIN_RAM_GB
        info(f"memory: sized for {data['host_ram_capacity']} GB ({_plan(data['host_ram_capacity'])})")
        return
    print(f"\n  This host has {have} GB of memory. fabric sizes its containers for what it may use: with all "
          f"{have} GB, {_plan(have)};\n  the rest stays with the system. Give less to leave room for other work.")
    while True:
        answer = input(f"  GB of memory fabric may use [{have}]: ").strip() or str(have)
        if answer.isdigit() and MIN_RAM_GB <= int(answer) <= have:
            data["host_ram_capacity"] = int(answer)
            return
        print(f"  a whole number from {MIN_RAM_GB} to {have}")
