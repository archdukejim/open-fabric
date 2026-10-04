import os

from fabriclib.vault.common.load_pkcs11 import load_pkcs11
from fabriclib.vault.common.pkcs11_modules import pkcs11_modules


def list_pkcs11_tokens(v):
    """Purpose: list the security keys / smart cards visible through the allowed PKCS#11 libraries; read-only.
    Inputs:  v — vars (openbao_pkcs11_modules, through pkcs11_modules).
    Returns: [{module, library, serial, label, manufacturer, model, pin_state}]; pin_state is "ok", "saw a wrong PIN",
             "last try" or "locked". Uninitialised tokens (e.g. SoftHSM's spare slot) are left out.
    Fails:   never — a library that cannot load or list (no PyKCS11, no pcscd or reader) or a slot that errors is
             skipped. No login, nothing written.
    Feeds:   `fabricctl vault tokens` and `add-key` (run_vault_command), detect_devices (given vars),
             tests/openbao/run.py.
    """
    out = []
    for module in pkcs11_modules(v):
        try:
            P, lib = load_pkcs11(module)
            slots = lib.getSlotList(tokenPresent=True)
        except Exception:               # a library without its daemon (pcscd) or reader: skip it
            continue
        for slot in slots:
            try:
                info = lib.getTokenInfo(slot)
            except Exception:
                continue
            flags = info.flags
            if not flags & P.CKF_TOKEN_INITIALIZED:     # blank (e.g. SoftHSM's spare slot): nothing to use
                continue
            state = ("locked" if flags & P.CKF_USER_PIN_LOCKED else "last try" if flags & P.CKF_USER_PIN_FINAL_TRY
                     else "saw a wrong PIN" if flags & P.CKF_USER_PIN_COUNT_LOW else "ok")
            out.append({"module": module, "library": os.path.basename(module),
                        "serial": info.serialNumber.strip(), "label": info.label.strip(),
                        "manufacturer": info.manufacturerID.strip(), "model": info.model.strip(),
                        "pin_state": state})
    return out
