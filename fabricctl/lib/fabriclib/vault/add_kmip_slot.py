import datetime
import os
import re
import secrets
import ssl
import tempfile

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.common.write_slot_store import write_slot_store
from fabriclib.vault.slots import kmip

LABEL_RE = re.compile(r"^[\w .,'()-]{0,60}$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
UID_RE = re.compile(r"^[\x21-\x7e]{1,128}$")


def _check_pems(ca_pem, cert_pem, key_pem):
    """The PEMs parse and the client key matches its certificate."""
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for name, text in (("ca.crt", ca_pem), ("client.crt", cert_pem), ("client.key", key_pem)):
            paths[name] = os.path.join(d, name)
            with open(paths[name], "w") as f:
                f.write(text or "")
        try:
            ssl.create_default_context(cafile=paths["ca.crt"])
        except (ssl.SSLError, ValueError):
            raise ValidationError("the server CA certificate is not a PEM certificate")
        try:
            ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_cert_chain(paths["client.crt"], paths["client.key"])
        except (ssl.SSLError, ValueError):
            raise ValidationError("the client certificate and key are not PEM, or do not belong together")


def add_kmip_slot(v, actor, endpoint, key_uid, ca_pem, cert_pem, key_pem, server_name="", label="", source="web"):
    """Make an HSM / key manager (any KMIP server) an unlock method.

    `endpoint` is host:port (5696 by default on devices); `key_uid` an
    active AES-256 key on the device that fabric's client may use for
    Encrypt/Decrypt; `ca_pem` verifies the device's TLS certificate (for
    `server_name`, default the host); `cert_pem`/`key_pem` are fabric's
    client certificate registered on the device (e.g. made under Step-CA →
    New key + certificate). The vault key is wrapped by the device,
    unwrapped again and checked before the method is saved. Returns the
    slot id."""
    host, _, port = (endpoint or "").strip().rpartition(":")
    if not HOST_RE.match(host) or not port.isdigit() or not 0 < int(port) < 65536:
        raise ValidationError("endpoint: host:port, e.g. kms.lan:5696")
    if not UID_RE.match(key_uid or ""):
        raise ValidationError("key id: the device's unique identifier of the AES key (printable, at most 128)")
    if server_name and not HOST_RE.match(server_name):
        raise ValidationError("server name: a DNS name")
    if not LABEL_RE.match(label or ""):
        raise ValidationError("label: letters, digits and simple punctuation, at most 60")
    _check_pems(ca_pem, cert_pem, key_pem)
    store = read_slot_store(v)
    if not store:
        raise ValidationError("no vault key yet: run `sudo fabricctl setup` first")
    if any(s["type"] == "kmip" and s["device"].get("endpoint") == f"{host}:{port}"
           and s["device"].get("key_uid") == key_uid for s in store["slots"]):
        raise ValidationError("that device key is already an unlock method")
    vault_key, _ = obtain_key(v, store, store["key_id"], attended=True)
    if vault_key is None:
        raise ValidationError("no unlock method is present to vouch for the new one")
    slot_id = f"hsm-{secrets.token_hex(3)}"
    slot = {"id": slot_id, "type": "kmip", "label": label or f"KMIP {host}",
            "added": datetime.date.today().isoformat(),
            "device": {"endpoint": f"{host}:{port}", "server_name": server_name or host, "key_uid": key_uid,
                       "summary": f"KMIP {host}:{port} · key {key_uid[:24]}",
                       "detail": "the key never leaves the device; revoke fabric's client there to lock the vault"},
            "wraps": {}}
    d = kmip.slot_dir(v, slot)
    os.makedirs(d, mode=0o700, exist_ok=True)
    for name, text in (("ca.crt", ca_pem), ("client.crt", cert_pem), ("client.key", key_pem)):
        write_private_file(os.path.join(d, name), text.encode(), 0, 0, 0o400)
    try:
        slot["wraps"][store["key_id"]] = kmip.wrap(v, slot, vault_key, store["key_id"])
        if kmip.unwrap(v, slot, slot["wraps"][store["key_id"]]) != vault_key:
            raise ValidationError("the key unwrapped by the device does not match; the method was not added")
    except ValidationError:
        kmip.discard(v, slot)
        raise
    except Exception as exc:
        kmip.discard(v, slot)
        raise ValidationError(f"the device refused Encrypt/Decrypt with key {key_uid}: {exc}")
    store["slots"].append(slot)
    write_slot_store(v, store, vault_key)
    write_audit(actor, "VAULT_SLOT_ADD", f"slot={slot_id} type=kmip endpoint={host}:{port} key={key_uid}", source)
    return slot_id
