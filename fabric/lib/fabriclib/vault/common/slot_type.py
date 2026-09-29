import importlib

from fabriclib.common.errors import ValidationError

TYPES = ("local", "usb", "pkcs11", "kmip")


def slot_type(name):
    """The module implementing a slot type (fabriclib/vault/slots/<name>.py:
    wrap, unwrap, present, forget, TESTED)."""
    if name not in TYPES:
        raise ValidationError(f"unknown unlock method type {name!r}")
    return importlib.import_module(f"fabriclib.vault.slots.{name}")
