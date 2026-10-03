import importlib

from fabriclib.common.errors import ValidationError

TYPES = ("local", "usb", "pkcs11", "kmip")


def slot_type(name):
    """Purpose: the module that implements one unlock-method type.
    Inputs:  name — the type name from the store; must be one of TYPES: local, usb, pkcs11, kmip.
    Returns: the module fabriclib.vault.slots.<name> (wrap, unwrap, present, forget, optional discard, TESTED).
    Fails:   ValidationError "unknown unlock method type"; ImportError if that module cannot be imported.
    Feeds:   obtain_key, list_slots, remove_slot, rotate_vault_key, vault_device_event.
    Notes:   the fixed TYPES list keeps a name read from the store from importing any other module.
    """
    if name not in TYPES:
        raise ValidationError(f"unknown unlock method type {name!r}")
    return importlib.import_module(f"fabriclib.vault.slots.{name}")
