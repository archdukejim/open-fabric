from agent.read_text import read_text
from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.vault.add_kmip_slot import add_kmip_slot
from fabriclib.vault.add_security_key_slot import add_security_key_slot
from fabriclib.vault.add_usb_slot import add_usb_slot
from fabriclib.vault.remove_slot import remove_slot
from fabriclib.vault.rotate_vault_key import rotate_vault_key
from fabriclib.vault.run_vault_command import restart_openbao
from fabriclib.vault.test_slot import test_slot


def post_vault(route, actor, data):
    """Purpose: changes to OpenBao's unlock methods, POST /v1/vault/... (fabriclib.vault).
    Inputs:  route — segments after "vault": ["slots","add-usb"], ["slots","add-hsm"], ["slots","add-security-key"],
             ["slots",<id>,"test"], ["slots",<id>,"remove"], ["rotate"]; actor — str; data — body (disk, label,
             endpoint, key_id, ca, cert, key, server_name, module, token, pin as each needs).
    Returns: {"id": slot id} for an add; {"ok": bool} for test and remove; rotate_vault_key's result for rotate (it
             restarts OpenBao through restart_openbao).
    Fails:   ValidationError("unknown operation") for another route, or from the readers and fabriclib (-> 400).
    Feeds:   agent/post_route.py (POST vault/...)."""
    v = load_vars()
    if route == ["slots", "add-usb"]:
        return {"id": add_usb_slot(v, actor, read_text(data, "disk"), read_text(data, "label"))}
    if route == ["slots", "add-hsm"]:
        return {"id": add_kmip_slot(v, actor, read_text(data, "endpoint"), read_text(data, "key_id"),
                                    read_text(data, "ca"), read_text(data, "cert"), read_text(data, "key"),
                                    read_text(data, "server_name"), read_text(data, "label"))}
    if route == ["slots", "add-security-key"]:
        return {"id": add_security_key_slot(v, actor, read_text(data, "module"), read_text(data, "token"),
                                            read_text(data, "pin"), read_text(data, "key_id") or "new",
                                            read_text(data, "label"))}
    if len(route) == 3 and route[0] == "slots" and route[2] == "test":
        return {"ok": test_slot(v, actor, route[1])}
    if len(route) == 3 and route[0] == "slots" and route[2] == "remove":
        remove_slot(v, actor, route[1])
        return {"ok": True}
    if route == ["rotate"]:
        return rotate_vault_key(v, actor, lambda: restart_openbao(v))
    raise ValidationError("unknown operation")
