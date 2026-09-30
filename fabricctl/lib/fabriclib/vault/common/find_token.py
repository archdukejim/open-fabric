from fabriclib.vault.common.load_pkcs11 import load_pkcs11


def find_token(module, serial):
    """Purpose: find a plugged-in PKCS#11 token by its serial number in one library, without logging in.
    Inputs:  module — path of a PKCS#11 library (callers pass only allowed ones: loading runs its code as root);
             serial — token serial (str), compared with the token's serialNumber stripped of padding.
    Returns: (PyKCS11 module, loaded library, slot, token info), or None when no present token has that serial.
    Fails:   ValidationError from load_pkcs11 if python3-pykcs11 is missing; PyKCS11.PyKCS11Error if the library
             cannot be loaded or queried (e.g. its reader daemon is not running).
    Feeds:   pkcs11_session, slots/pkcs11.present.
    """
    P, lib = load_pkcs11(module)
    for slot in lib.getSlotList(tokenPresent=True):
        info = lib.getTokenInfo(slot)
        if info.serialNumber.strip() == serial:
            return P, lib, slot, info
    return None
