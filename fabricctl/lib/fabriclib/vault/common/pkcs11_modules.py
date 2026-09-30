import glob

# Vendor PKCS#11 libraries fabric looks for (Debian/Ubuntu paths, any arch).
DEFAULT_MODULES = ["/usr/lib/*/libykcs11.so*",              # YubiKey PIV (package ykcs11)
                   "/usr/lib/*/opensc-pkcs11.so",           # OpenSC: Nitrokey, SmartCard-HSM, most smart cards
                   "/usr/lib/*/pkcs11/opensc-pkcs11.so",
                   "/usr/lib/softhsm/libsofthsm2.so"]       # SoftHSM2 (software token: tests, not a device)


def pkcs11_modules(v):
    """The PKCS#11 libraries fabric may load: paths or globs from
    `openbao_pkcs11_modules` (root-owned vars; never from a request — loading
    a library runs its code as root), resolved to files that exist."""
    out = []
    for pattern in v.get("openbao_pkcs11_modules") or DEFAULT_MODULES:
        for path in sorted(glob.glob(pattern)):
            if path not in out:
                out.append(path)
    return out
