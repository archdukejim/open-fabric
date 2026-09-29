import datetime
import os
import re

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.pkcs11_modules import pkcs11_modules
from fabriclib.vault.common.pkcs11_session import pkcs11_session
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.write_slot_store import write_slot_store
from fabriclib.vault.detect_devices import detect_devices
from fabriclib.vault.slots import pkcs11
from fabriclib.vault.write_device_rules import write_device_rules

LABEL_RE = re.compile(r"^[\w .,'()-]{0,60}$")
KEY_ID_RE = re.compile(r"^(new|[0-9a-f]{2}([0-9a-f]{2}){0,31})$")
KEY_LABEL = "fabric-vault"


def _generate(P, session):
    """A new RSA-2048 pair on the token: private part sensitive and not
    extractable. Returns its CKA_ID (hex)."""
    ident = tuple(os.urandom(8))
    common = [(P.CKA_TOKEN, True), (P.CKA_LABEL, KEY_LABEL), (P.CKA_ID, ident)]
    try:
        session.generateKeyPair(
            [(P.CKA_CLASS, P.CKO_PUBLIC_KEY), (P.CKA_ENCRYPT, True), (P.CKA_MODULUS_BITS, 2048),
             (P.CKA_PUBLIC_EXPONENT, (1, 0, 1))] + common,
            [(P.CKA_CLASS, P.CKO_PRIVATE_KEY), (P.CKA_PRIVATE, True), (P.CKA_SENSITIVE, True),
             (P.CKA_EXTRACTABLE, False), (P.CKA_DECRYPT, True)] + common,
            mecha=P.MechanismRSAGENERATEKEYPAIR)
    except P.PyKCS11Error as exc:
        raise ValidationError(f"the token would not make a key pair through PKCS#11 ({exc}). Create an RSA-2048 "
                              "key with the vendor tool (YubiKey: `ykman piv keys generate` in slot 9d, "
                              "optionally with --touch-policy), then add it by its key id (9d is id 03)")
    return bytes(ident).hex()


def _check_existing(P, session, key_id):
    ident = tuple(bytes.fromhex(key_id))
    private = session.findObjects([(P.CKA_CLASS, P.CKO_PRIVATE_KEY), (P.CKA_ID, ident)])
    public = session.findObjects([(P.CKA_CLASS, P.CKO_PUBLIC_KEY), (P.CKA_ID, ident)])
    if not private or not public:
        raise ValidationError(f"no key pair with id {key_id} on the token")
    sensitive, extractable, key_type = session.getAttributeValue(
        private[0], [P.CKA_SENSITIVE, P.CKA_EXTRACTABLE, P.CKA_KEY_TYPE])
    if key_type != P.CKK_RSA:
        raise ValidationError("the key must be RSA (the wrap is RSA-OAEP)")
    if not sensitive or extractable:
        raise ValidationError("that private key can be exported from the token: not accepted")


def add_security_key_slot(v, actor, module, token_serial, pin, key_id="new", label="", source="web"):
    """Make a PKCS#11 security key an unlock method.

    `module` must be one of the allowed libraries; the token is found by its
    serial. With key_id "new" the token makes an RSA-2048 key pair that can
    never leave it; otherwise the existing pair with that CKA_ID is used
    (sensitive, not extractable). The vault key is wrapped by the token,
    unwrapped again and checked before the method is saved. The PIN is kept
    root-only on this host. Returns the new slot id."""
    if module not in pkcs11_modules(v):
        raise ValidationError("that PKCS#11 library is not on the allowed list (openbao_pkcs11_modules)")
    if not LABEL_RE.match(label or ""):
        raise ValidationError("label: letters, digits and simple punctuation, at most 60")
    if not (4 <= len(pin or "") <= 64) or not pin.isprintable():
        raise ValidationError("PIN: 4 to 64 printable characters")
    key_id = (key_id or "new").lower()
    if not KEY_ID_RE.match(key_id):
        raise ValidationError("key id: `new` or the key's CKA_ID in hex (e.g. 03)")
    store = read_slot_store(v)
    if not store:
        raise ValidationError("no vault key yet: run `sudo fabricctl setup` first")
    if any(s["type"] == "pkcs11" and s["device"].get("token_serial") == token_serial
           and s["device"].get("module") == module for s in store["slots"]):
        raise ValidationError("this security key is already an unlock method")
    vault_key, _ = obtain_key(v, store, store["key_id"], attended=True)
    if vault_key is None:
        raise ValidationError("no unlock method is present to vouch for the new one")
    with pkcs11_session(module, token_serial, pin, attended=True) as (P, session, info):
        if key_id == "new":
            key_id = _generate(P, session)
        else:
            _check_existing(P, session, key_id)
        maker, model = info.manufacturerID.strip(), info.model.strip()
    usb = [t for t in detect_devices()["tokens"] if t["serial"] and t["serial"].lstrip("0") == token_serial.lstrip("0")]
    slot_id = f"key-{token_serial[-8:].lower()}-{key_id[-4:]}"
    slot = {"id": slot_id, "type": "pkcs11", "label": label or f"{maker} {model}".strip(),
            "added": datetime.date.today().isoformat(),
            "device": {"module": module, "token_serial": token_serial, "key_id": key_id,
                       "usb_serial": usb[0]["serial"] if len(usb) == 1 else "",
                       "summary": f"{maker} {model} · serial {token_serial} · key {key_id}",
                       "detail": "the key cannot be copied; its PIN is kept root-only on this host"
                                 + ("" if len(usb) == 1 else " · kill switch off: USB device not matched")},
            "wraps": {}}
    pkcs11.save_pin(v, slot, pin)
    try:
        slot["wraps"][store["key_id"]] = pkcs11.wrap(v, slot, vault_key, store["key_id"])
        if pkcs11.unwrap(v, slot, slot["wraps"][store["key_id"]], attended=True) != vault_key:
            raise ValidationError("the key unwrapped by the token does not match; the key was not added")
    except Exception:
        pkcs11.discard(v, slot)
        raise
    store["slots"].append(slot)
    write_slot_store(v, store, vault_key)
    write_device_rules(v)
    write_audit(actor, "VAULT_SLOT_ADD", f"slot={slot_id} type=pkcs11 token={maker} {model} serial={token_serial} "
                                         f"key={key_id}", source)
    return slot_id
