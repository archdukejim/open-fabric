import glob
import json
import os
import subprocess

# USB vendor ids of security keys fabric recognises by name (any other
# PKCS#11 token is still usable through its vendor library).
TOKEN_VENDORS = {"1050": "Yubico", "20a0": "Nitrokey", "04e6": "SCM/Identiv", "096e": "Feitian",
                 "08e6": "Gemalto", "0529": "SafeNet (Aladdin)"}


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _tokens(sys_root):
    out = []
    for dev in sorted(glob.glob(os.path.join(sys_root, "bus/usb/devices/*"))):
        vendor = _read(os.path.join(dev, "idVendor")).lower()
        if vendor not in TOKEN_VENDORS:
            continue
        out.append({"vendor": TOKEN_VENDORS[vendor], "product": _read(os.path.join(dev, "product")) or "security key",
                    "serial": _read(os.path.join(dev, "serial")), "usb_id": f"{vendor}:{_read(os.path.join(dev, 'idProduct'))}",
                    "port": os.path.basename(dev)})
    return out


def _disks():
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


def detect_devices(sys_root="/sys"):
    """Unlock-capable devices plugged into this host, read-only: security
    keys (by USB vendor, with serial) and USB disks (model, serial, size,
    filesystem UUIDs). Nothing is opened, mounted or written."""
    return {"tokens": _tokens(sys_root), "disks": _disks()}
