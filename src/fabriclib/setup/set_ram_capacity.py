from fabriclib.common.console import info
from fabriclib.setup.errors import SetupError
from fabriclib.system.host_ram_gb import host_ram_gb

MIN_RAM_GB = 4                      # 2.1.2.3: a Raspberry Pi with 4 GB is the smallest host


def _plan(gb):
    """Purpose: what fabric's largest containers may use at a size, as the compose files set it (manual 1.2.4.2).
    Inputs:  gb — int, host_ram_capacity.
    Returns: str, e.g. "Keycloak 2400 MB, the domain controller 1024 MB, Postgres 400 MB, BIND 256 MB".
    Fails:   never.
    Feeds:   set_ram_capacity."""
    f = gb / 4
    return (f"Keycloak {int(1200 * f)} MB, the domain controller {int(512 * f)} MB, Postgres {int(200 * f)} MB, "
            f"BIND {int(128 * f)} MB")


def set_ram_capacity(data):
    """Purpose: how much of this host fabric sizes itself for (2.1.2.3, manual 1.2.4.2): all of the measured memory
             unless set, no longer asked (2.1.2.16); less restricts fabric, leaving the rest to other work on the
             host. Kept as host_ram_capacity: change it with the vars editor (`sudo fabricctl`) or a vars file.
    Inputs:  data — the settings so far (changed: host_ram_capacity).
    Returns: None.
    Fails:   SetupError when the host has less than 4 GB, or a host_ram_capacity set is under 4 or more than the
             host has.
    Feeds:   collect_vars."""
    have = host_ram_gb()
    if have and have < MIN_RAM_GB:
        raise SetupError(f"this host has {have} GB of memory: fabric needs at least {MIN_RAM_GB} GB (2.1.2.3)")
    set_ = int(data.get("host_ram_capacity") or 0)
    if set_:
        if set_ < MIN_RAM_GB or (have and set_ > have):
            raise SetupError(f"host_ram_capacity is {set_} GB: give {MIN_RAM_GB} to {have or 'the host'}'s GB")
        return
    data["host_ram_capacity"] = have or MIN_RAM_GB
    info(f"memory: sized for {data['host_ram_capacity']} GB ({_plan(data['host_ram_capacity'])}); give fabric less "
         "with the vars editor")
