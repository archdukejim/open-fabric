import json
import subprocess


def block_device(path=None, fs_uuid=None):
    """lsblk facts for a whole disk given its path, or for the disk holding the
    file system with `fs_uuid`: {path, fs_path, model, serial, tran, rm, uuid,
    mounted: [mountpoints of it and its partitions]} or None. Read-only."""
    res = subprocess.run(["lsblk", "-J", "-p", "-o", "NAME,PATH,MODEL,SERIAL,TRAN,RM,TYPE,UUID,MOUNTPOINTS"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return None
    for disk in json.loads(res.stdout).get("blockdevices", []):
        nodes = [disk] + list(disk.get("children") or [])
        mounted = [m for n in nodes for m in (n.get("mountpoints") or []) if m]
        facts = {"path": disk.get("path"), "model": (disk.get("model") or "").strip(), "serial": disk.get("serial") or "",
                 "tran": disk.get("tran") or "", "rm": bool(disk.get("rm")), "mounted": mounted}
        if path and disk.get("path") == path:
            return dict(facts, fs_path=disk.get("path"), uuid=disk.get("uuid") or "")
        if fs_uuid:
            for n in nodes:
                if n.get("uuid") == fs_uuid:
                    return dict(facts, fs_path=n.get("path"), uuid=fs_uuid)
    if fs_uuid:
        # lsblk reads udev's database, which lags right after a device appears;
        # blkid probes the devices themselves.
        probe = subprocess.run(["blkid", "-t", f"UUID={fs_uuid}", "-o", "device"], capture_output=True, text=True)
        dev = probe.stdout.split()[0] if probe.returncode == 0 and probe.stdout.strip() else ""
        if dev:
            disk = next((d for d in json.loads(res.stdout).get("blockdevices", [])
                         if d.get("path") == dev or any(c.get("path") == dev for c in d.get("children") or [])), {})
            return {"path": disk.get("path", dev), "fs_path": dev, "model": (disk.get("model") or "").strip(),
                    "serial": disk.get("serial") or "", "tran": disk.get("tran") or "", "rm": bool(disk.get("rm")),
                    "mounted": [], "uuid": fs_uuid}
    return None
