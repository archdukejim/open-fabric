import re


def normalize_mac(text):
    """Any common MAC spelling (aa-bb-cc-dd-ee-ff, AABB.CCDD.EEFF,
    aabbccddeeff) -> aa:bb:cc:dd:ee:ff, as fabric stores it; None if it is
    not a MAC."""
    hexits = re.sub(r"[^0-9a-f]", "", str(text or "").lower())
    if len(hexits) != 12 or len(re.sub(r"[0-9a-f:.\-\s]", "", str(text).lower())):
        return None
    return ":".join(hexits[i:i + 2] for i in range(0, 12, 2))
