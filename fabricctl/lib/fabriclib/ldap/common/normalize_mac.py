import re

from fabriclib.common.errors import ValidationError


def normalize_mac(mac):
    """Purpose: Bring a MAC address into the one spelling the directory stores.
    Inputs:  mac — any value; colons, dashes, Cisco dots, spaces or bare hex are accepted.
    Returns: "aa:bb:cc:dd:ee:ff" (lower case).
    Fails:   ValidationError "not a MAC address: ..." (not 12 hex digits); "... is a multicast address, not
             a device".
    Feeds:   common/check_device_fields.
    """
    hexdigits = re.sub(r"[:\-.\s]", "", str(mac)).lower()
    if not re.fullmatch(r"[0-9a-f]{12}", hexdigits):
        raise ValidationError(f"not a MAC address: {mac!r}")
    if int(hexdigits[1], 16) & 1:
        raise ValidationError(f"{mac} is a multicast address, not a device")
    return ":".join(hexdigits[i:i + 2] for i in range(0, 12, 2))
