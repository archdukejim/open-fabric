import json
import subprocess


def block_device(path=None, fs_uuid=None):
    """Purpose: look up one disk's facts with lsblk, by the disk's path or by a file-system UUID on it. Read-only.
    Inputs:  path — whole-disk device path (e.g. /dev/sdb; a partition path does not match), or None;
             fs_uuid — file-system UUID to find on a disk or one of its partitions, or None.
             Runs lsblk (udev's database) and, for fs_uuid not found there, blkid.
    Returns: {path (the disk), fs_path (the node holding the file system), model, serial, tran, rm (bool), uuid,
             mounted: [mountpoints of the disk and its partitions]}; or None when nothing matches or lsblk fails.
             In the blkid fallback `mounted` is always [].
    Fails:   FileNotFoundError if lsblk or blkid is not installed; ValueError if lsblk prints something not JSON.
             A non-zero lsblk exit gives None, not an error.
    Feeds:   add_usb_slot (by path: is it a whole, unmounted USB disk), slots/usb._stick (by fs_uuid).
    Notes:   lsblk reads udev's database, which lags right after a device appears; blkid probes the devices.
    """
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
