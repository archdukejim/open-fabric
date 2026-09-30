"""fabric policy's connection to 389-DS: verified LDAPS, as the read-only
cn=radius_reader (one connection per FreeRADIUS thread), or as a person to
check their password."""
import json
import threading

import ldap

CONFIG = "/etc/freeradius/fabric/fabric-radius.json"
_local = threading.local()
_conf = {}


def load_config():
    if not _conf:
        with open(CONFIG) as f:
            _conf.update(json.load(f))
        with open(_conf["password_file"]) as f:
            _conf["password"] = f.read().strip()
    return _conf


def connect(dn=None, password=None):
    conf = load_config()
    c = ldap.initialize(conf["uri"])
    c.set_option(ldap.OPT_X_TLS_CACERTFILE, conf["ca_file"])
    c.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
    c.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
    # short: a switch waits a few seconds; the directory down must still answer Reject in time
    c.set_option(ldap.OPT_NETWORK_TIMEOUT, 2)
    c.set_option(ldap.OPT_TIMEOUT, 3)
    c.set_option(ldap.OPT_REFERRALS, 0)
    c.simple_bind_s(dn or conf["bind_dn"], conf["password"] if dn is None else password)
    return c


def search(base, filterstr, attrs):
    """One search on this thread's connection; reconnects once if 389-DS
    restarted since. Any other LDAP error propagates (the caller refuses)."""
    for attempt in (1, 2):
        c = getattr(_local, "conn", None)
        try:
            if c is None:
                c = _local.conn = connect()
            return c.search_s(base, ldap.SCOPE_ONELEVEL, filterstr, attrs)
        except (ldap.SERVER_DOWN, ldap.CONNECT_ERROR, ldap.TIMEOUT):
            _local.conn = None
            if attempt == 2:
                raise


