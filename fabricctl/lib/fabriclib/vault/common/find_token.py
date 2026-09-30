from fabriclib.vault.common.load_pkcs11 import load_pkcs11


def find_token(module, serial):
    """(PyKCS11, lib, slot, token info) for the token with `serial` in
    `module`, or None if it is not plugged in."""
    P, lib = load_pkcs11(module)
    for slot in lib.getSlotList(tokenPresent=True):
        info = lib.getTokenInfo(slot)
        if info.serialNumber.strip() == serial:
            return P, lib, slot, info
    return None
