from fabriclib.common.errors import ValidationError


def load_pkcs11(module):
    """PyKCS11 and the loaded library (python3-pykcs11 is a Recommends of the package)."""
    try:
        import PyKCS11
    except ImportError:
        raise ValidationError("security keys need python3-pykcs11: sudo apt install python3-pykcs11")
    lib = PyKCS11.PyKCS11Lib()
    lib.load(module)
    return PyKCS11, lib
