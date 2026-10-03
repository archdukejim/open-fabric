from fabriclib.common.errors import ValidationError


def load_pkcs11(module):
    """Purpose: import PyKCS11 and load one PKCS#11 library.
    Inputs:  module — path of the library; loading runs its code as root, so callers pass only allowed paths.
    Returns: (PyKCS11 module, PyKCS11Lib with the library loaded).
    Fails:   ValidationError if python3-pykcs11 (a Recommends of the package) is not installed;
             PyKCS11.PyKCS11Error if the library cannot be loaded.
    Feeds:   find_token, list_pkcs11_tokens.
    """
    try:
        import PyKCS11
    except ImportError:
        raise ValidationError("security keys need python3-pykcs11: sudo apt install python3-pykcs11")
    lib = PyKCS11.PyKCS11Lib()
    lib.load(module)
    return PyKCS11, lib
