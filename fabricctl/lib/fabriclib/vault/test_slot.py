from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.read_slot_store import read_slot_store


def test_slot(v, actor, slot_id, source="web"):
    """Purpose: unwrap the vault key through one unlock method and check it against the stored check value.
             Nothing is written or started (except the audit line).
    Inputs:  v — vars; actor — who asked (audit); slot_id — the method to test; source — audit source ("web").
    Returns: True.
    Fails:   ValidationError: no such method; it could not unwrap the key (with the first reason obtain_key recorded).
    Feeds:   agent route POST /v1/vault/slots/<id>/test, `fabricctl vault test` (run_vault_command),
             tests/openbao/run.py.
    Notes:   attended: a security key that saw a wrong PIN is still tried; a correct login clears that state.
             Audited as VAULT_SLOT_TEST, ok or FAILED.
    """
    store = read_slot_store(v)
    if not store or not any(s["id"] == slot_id for s in store["slots"]):
        raise ValidationError(f"no unlock method {slot_id!r}")
    errors = []
    key, _ = obtain_key(v, store, store["key_id"], only=slot_id, attended=True, errors=errors)
    write_audit(actor, "VAULT_SLOT_TEST", f"slot={slot_id} {'ok' if key else 'FAILED'}", source)
    if key is None:
        why = errors[0].split(": ", 1)[-1] if errors else "device missing, locked or wrong"
        raise ValidationError(f"this method could not unwrap the vault key ({why})")
    return True
