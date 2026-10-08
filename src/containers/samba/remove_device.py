from paths import devices_dn


def remove_device(samdb, lp, site, name):
    """Purpose: a device of this site removed (its roles go with it: they are the device's own attribute).
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str; name — the device's name.
    Returns: {"name"}.
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT, ERR_INSUFFICIENT_ACCESS_RIGHTS.
    Feeds:   directory_ops (op "remove_device")."""
    samdb.delete(f"CN={name},{devices_dn(samdb, site)}")
    return {"name": name}
