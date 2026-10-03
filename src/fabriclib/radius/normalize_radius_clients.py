import ipaddress
import re

from fabriclib.common.errors import ValidationError

NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
# A secret a switch's CLI takes without quoting: printable ASCII without spaces,
# quotes, backslashes or `$` (FreeRADIUS expands ${...} inside quoted strings).
SECRET_RE = re.compile(r"^[A-Za-z0-9!#%&()*+,./:;<=>?@\[\]^_{|}~-]{16,128}$")


def normalize_radius_clients(clients):
    """Purpose: Check radius_clients, the switches and access points that may ask FreeRADIUS.
    Inputs:  clients — list of {name, address, message_authenticator (default true), secret (optional: one a switch
             already has)}, or None.
    Returns: (clients, {name: secret}): entries {"name" (lower case), "address" (a single IP or a network),
             "message_authenticator" (bool)}, and the secrets taken out of them, to be kept in fabric's secrets.
    Fails:   ValidationError: an entry that is not a dict, a bad name, a name listed twice, an address that is not an IP
             or network (host bits must be zero), 0/0, overlapping clients, or a bad secret.
    Feeds:   deploy/merge_radius_clients (apply), add_radius_client; SECRET_RE is reused by rotate_radius_secret; tests/freeradius/run.py,
             tests/render.py.
    Notes:   SECRET_RE keeps a secret typeable on a switch CLI without quoting and free of `$` (FreeRADIUS expands
             ${...} inside quoted strings).
    """
    out, embedded, seen_names, seen_nets = [], {}, set(), []
    for c in clients or []:
        if not isinstance(c, dict):
            raise ValidationError("radius_clients: each entry is {name, address}")
        name = str(c.get("name", "")).strip().lower()
        if not NAME_RE.match(name):
            raise ValidationError(f"radius_clients: {name!r} is not a name (a-z, 0-9, -; up to 32)")
        if name in seen_names:
            raise ValidationError(f"radius_clients: {name} is listed twice")
        try:
            net = ipaddress.ip_network(str(c.get("address", "")).strip(), strict=True)
        except ValueError:
            raise ValidationError(f"radius_clients: {name}: address must be an IP address or network "
                                  f"(e.g. 192.168.4.2 or 192.168.10.0/24)")
        if net.prefixlen == 0:
            raise ValidationError(f"radius_clients: {name}: 'any address' is not a RADIUS client")
        for other, onet in seen_nets:
            if net.version == onet.version and net.overlaps(onet):
                raise ValidationError(f"radius_clients: {name} and {other} overlap")
        entry = {"name": name, "address": str(net.network_address) if net.num_addresses == 1 else str(net),
                 "message_authenticator": bool(c.get("message_authenticator", True))}
        secret = c.get("secret")
        if secret:
            if not SECRET_RE.match(str(secret)):
                raise ValidationError(f"radius_clients: {name}: the secret must be 16-128 printable characters, "
                                      f"without spaces or quotes")
            embedded[name] = str(secret)
        seen_names.add(name)
        seen_nets.append((name, net))
        out.append(entry)
    return out, embedded
