from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB


def open_samdb(conf, schema_updates=False):
    """Purpose: the DC's own database, opened locally as the system (the converge code runs as root inside the DC:
             no credentials, no network).
    Inputs:  conf — str, the DC's smb.conf; schema_updates — bool, allow changes to the schema (fabric's and sudo's
             classes are added that way).
    Returns: (SamDB, LoadParm).
    Fails:   ldb.LdbError if the database cannot be opened; RuntimeError from LoadParm for an unreadable smb.conf.
    Feeds:   converge, ensure_schema."""
    lp = LoadParm()
    lp.load(conf)
    if schema_updates:
        lp.set("dsdb:schema update allowed", "true")
    return SamDB(url=lp.private_path("sam.ldb"), session_info=system_session(), lp=lp), lp
