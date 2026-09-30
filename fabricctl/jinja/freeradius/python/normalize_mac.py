import re


def normalize_mac(text):
    """Purpose: any common MAC spelling (aa-bb-cc-dd-ee-ff, AABB.CCDD.EEFF, aabbccddeeff) to the form fabric
             stores, aa:bb:cc:dd:ee:ff.
    Inputs:  text — str or None; only hex digits and the separators ":", ".", "-" and whitespace are allowed.
    Returns: str "aa:bb:cc:dd:ee:ff"; None if it is not exactly 12 hex digits or has other characters.
    Fails:   never.
    Feeds:   fabric_radius.authorize (User-Name and Calling-Station-Id)."""
    hexits = re.sub(r"[^0-9a-f]", "", str(text or "").lower())
    if len(hexits) != 12 or len(re.sub(r"[0-9a-f:.\-\s]", "", str(text).lower())):
        return None
    return ":".join(hexits[i:i + 2] for i in range(0, 12, 2))
