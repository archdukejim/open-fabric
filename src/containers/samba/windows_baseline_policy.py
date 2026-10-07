from samba.dcerpc import misc, preg
from samba.ndr import ndr_pack

REGISTRY = "{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{0F6B957D-509E-11D1-A7CC-0000F87571E3}"   # Registry, Admin. Templates
SCRIPTS = "{42B5FAAE-6536-11D2-AE5A-0000F87571E3}{40B6664F-4972-11D1-A7CA-0000F87571E3}"    # Scripts, Startup/Shutdown
SCRIPT = ("@echo off\r\n"
          "rem fabric (manual 2.11.2.20): Wired AutoConfig on, fabric's 802.1X profile on every wired interface\r\n"
          "sc config dot3svc start= auto >nul\r\n"
          "net start dot3svc >nul 2>&1\r\n"
          "netsh lan add profile filename=\"%~dp0fabric-lan.xml\" >nul\r\n")


def _entry(key, name, kind, data):
    """Purpose: one Registry.pol value.
    Inputs:  key — the policy key; name — the value's name; kind — misc.REG_DWORD or REG_SZ; data — int or str.
    Returns: preg.entry.
    Fails:   never.
    Feeds:   windows_baseline_policy."""
    e = preg.entry()
    e.keyname, e.valuename, e.type, e.data = key, name, kind, data
    return e


def windows_baseline_policy(lan_profile, sso_host=""):
    """Purpose: the site's Windows baseline (manual 2.11.2.20, S5.2; the owner's direction, 5.8.1.17): what a joined
             machine needs to work at once, beside the trust GPO (fabric's root CA) and the site's log-on rights —
             it waits for the network at start-up and log-on (a domain person's first log-on needs the DC), keeps the
             domain's time (NT5DS: signed by its DC, D100) and, with FreeRADIUS on, runs Wired AutoConfig with
             fabric's 802.1X profile (a start-up script, `netsh lan add profile`). With Kerberos sign-in on, Edge,
             Chrome and Firefox may use the logon's ticket for Keycloak's name (manual 5.8.2.6.5, D117).
    Inputs:  lan_profile — str, the wired profile XML (fabriclib's windows_lan_profile "peap"), or "" without 802.1X;
             sso_host — Keycloak's name (sso.<domain>), or "" without Kerberos sign-in.
    Returns: (extensions str for gPCMachineExtensionNames, {path under the GPO folder: bytes}).
    Fails:   never.
    Feeds:   converge."""
    f = preg.file()
    f.header.signature, f.header.version = "PReg", 1
    entries = [_entry("Software\\Policies\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon", "SyncForegroundPolicy",
                      misc.REG_DWORD, 1),
               _entry("Software\\Policies\\Microsoft\\W32Time\\Parameters", "Type", misc.REG_SZ, "NT5DS")]
    if sso_host:                          # the browsers' Negotiate allowlists (Kerberos sign-in to Keycloak)
        entries += [_entry("Software\\Policies\\Microsoft\\Edge", "AuthServerAllowlist", misc.REG_SZ, sso_host),
                    _entry("Software\\Policies\\Google\\Chrome", "AuthServerAllowlist", misc.REG_SZ, sso_host),
                    _entry("Software\\Policies\\Mozilla\\Firefox\\Authentication\\SPNEGO", "1", misc.REG_SZ,
                           sso_host)]
    f.num_entries = len(entries)          # before the entries: NDR sizes the array by it
    f.entries = entries
    files = {"Machine/Registry.pol": ndr_pack(f)}
    if not lan_profile:
        return f"[{REGISTRY}]", files
    ini = "[Startup]\r\n0CmdLine=fabric-8021x.cmd\r\n0Parameters=\r\n"
    files.update({"Machine/Scripts/scripts.ini": b"\xff\xfe" + ini.encode("utf-16-le"),
                  "Machine/Scripts/Startup/fabric-8021x.cmd": SCRIPT.encode("ascii"),
                  "Machine/Scripts/Startup/fabric-lan.xml": lan_profile.encode("utf-8")})
    return f"[{REGISTRY}][{SCRIPTS}]", files
