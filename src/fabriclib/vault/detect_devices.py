import glob
import json
import os
import subprocess

# USB vendor ids of security keys fabric recognises by name (any other
# PKCS#11 token is still usable through its vendor library).
TOKEN_VENDORS = {"1050": "Yubico", "20a0": "Nitrokey", "04e6": "SCM/Identiv", "096e": "Feitian",
                 "08e6": "Gemalto", "0529": "SafeNet (Aladdin)"}


def _read(path):
    """Purpose: read one sysfs attribute.
    Inputs:  path — file path.
    Returns: its text, stripped; "" if it cannot be read.
    Fails:   never — OSError gives "".
    Feeds:   _tokens.
    """
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _tokens(sys_root):
    """Purpose: list USB security keys, recognised by vendor id in sysfs.
    Inputs:  sys_root — sysfs root ("/sys"; tests pass a fake tree).
    Returns: [{vendor, product, serial, usb_id "vvvv:pppp", port}] for devices whose vendor is in TOKEN_VENDORS.
    Fails:   never — unreadable attributes read as "".
    Feeds:   detect_devices.
    """
    out = []
    for dev in sorted(glob.glob(os.path.join(sys_root, "bus/usb/devices/*"))):
        vendor = _read(os.path.join(dev, "idVendor")).lower()
        if vendor not in TOKEN_VENDORS:
            continue
        out.append({"vendor": TOKEN_VENDORS[vendor], "product": _read(os.path.join(dev, "product")) or "security key",
                    "serial": _read(os.path.join(dev, "serial")),
                    "usb_id": f"{vendor}:{_read(os.path.join(dev, 'idProduct'))}",
                    "port": os.path.basename(dev)})
    return out


def _disks():
    """Purpose: list USB disks with lsblk.
    Inputs:  none.
    Returns: [{path, model, serial, size_gb, uuids, labels}] for devices of type disk on USB; [] if lsblk fails.
    Fails:   FileNotFoundError if lsblk is missing; ValueError if its output is not JSON.
    Feeds:   detect_devices.
    """
    res = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,MODEL,SERIAL,SIZE,TRAN,RM,TYPE,UUID,LABEL"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return []
    out = []
    for d in json.loads(res.stdout).get("blockdevices", []):
        if d.get("type") != "disk" or d.get("tran") != "usb":
            continue
        parts = d.get("children") or []
        out.append({"path": d.get("path"), "model": (d.get("model") or "USB disk").strip(),
                    "serial": d.get("serial") or "", "size_gb": round(int(d.get("size") or 0) / 1e9, 1),
                    "uuids": [p["uuid"] for p in parts if p.get("uuid")] or ([d["uuid"]] if d.get("uuid") else []),
                    "labels": [p["label"] for p in parts if p.get("label")]})
    return out


def detect_devices(sys_root="/sys", v=None):
    """Purpose: list the unlock-capable devices plugged into this host; read-only (nothing mounted, no login).
    Inputs:  sys_root — sysfs root ("/sys"); v — vars, or None to skip the PKCS#11 token listing.
    Returns: {"tokens": [security keys by USB vendor], "disks": [USB disks]} plus "pkcs11": list_pkcs11_tokens(v)
             when v is given.
    Fails:   as _disks; list_pkcs11_tokens skips libraries that fail.
    Feeds:   agent route GET /v1/vault/devices (web UI), add_security_key_slot (the token's USB serial for the kill
             switch).
    """
    out = {"tokens": _tokens(sys_root), "disks": _disks()}
    if v is not None:
        from fabriclib.vault.list_pkcs11_tokens import list_pkcs11_tokens
        out["pkcs11"] = list_pkcs11_tokens(v)
    return out
