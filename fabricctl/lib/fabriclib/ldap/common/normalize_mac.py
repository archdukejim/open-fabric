import re

from fabriclib.common.errors import ValidationError


def normalize_mac(mac):
    """aa:bb:cc:dd:ee:ff from any common spelling (colons, dashes, Cisco
    dots, bare hex); refuses anything else and multicast addresses."""
    hexdigits = re.sub(r"[:\-.\s]", "", str(mac)).lower()
    if not re.fullmatch(r"[0-9a-f]{12}", hexdigits):
        raise ValidationError(f"not a MAC address: {mac!r}")
    if int(hexdigits[1], 16) & 1:
        raise ValidationError(f"{mac} is a multicast address, not a device")
    return ":".join(hexdigits[i:i + 2] for i in range(0, 12, 2))
