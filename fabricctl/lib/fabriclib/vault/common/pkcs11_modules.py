import glob

# Vendor PKCS#11 libraries fabric looks for (Debian/Ubuntu paths, any arch).
DEFAULT_MODULES = ["/usr/lib/*/libykcs11.so*",              # YubiKey PIV (package ykcs11)
                   "/usr/lib/*/opensc-pkcs11.so",           # OpenSC: Nitrokey, SmartCard-HSM, most smart cards
                   "/usr/lib/*/pkcs11/opensc-pkcs11.so",
                   "/usr/lib/softhsm/libsofthsm2.so"]       # SoftHSM2 (software token: tests, not a device)


def pkcs11_modules(v):
    """Purpose: the PKCS#11 libraries fabric may load, resolved to files present on this host.
    Inputs:  v — vars: openbao_pkcs11_modules (paths or globs; root-owned vars, never from a request),
             else DEFAULT_MODULES (YubiKey ykcs11, OpenSC, SoftHSM2).
    Returns: list of existing library paths (str) without duplicates, in pattern order, sorted within a pattern.
    Fails:   never — a pattern that matches nothing adds nothing.
    Feeds:   add_security_key_slot (allowed-list check), list_pkcs11_tokens.
    Notes:   loading a library runs its code as root; that is why the list comes only from the host's vars.
    """
    out = []
    for pattern in v.get("openbao_pkcs11_modules") or DEFAULT_MODULES:
        for path in sorted(glob.glob(pattern)):
            if path not in out:
                out.append(path)
    return out
