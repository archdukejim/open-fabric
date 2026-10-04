"""The dev preview's sample data: what a small home install looks like (nothing here is real)."""

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]
SAMPLE_RADIUS = {"enabled": True, "server_name": "radius.home.arpa", "host_ip": "192.168.1.2",
                 "clients": [{"name": "switch1", "address": "192.168.1.3", "message_authenticator": True},
                             {"name": "ap-hall", "address": "192.168.1.4", "message_authenticator": False}],
                 "people": [{"group": "staff", "vlan": 20, "priority": 50},
                            {"group": "guests", "vlan": 50, "priority": 60}],
                 "log": [{"time": "2026-09-29T20:14:02", "decision": "ACCEPT", "method": "eap-tls",
                          "device": "jims-laptop", "vlan": "20", "mac": "02:11:22:33:44:55", "nas": "switch1",
                          "reason": ""},
                         {"time": "2026-09-29T20:13:10", "decision": "ACCEPT", "method": "eap-ttls", "device": "alice",
                          "person": True, "vlan": "20", "mac": "02:11:22:33:44:66", "nas": "ap-hall", "reason": ""},
                         {"time": "2026-09-29T20:12:40", "decision": "REJECT", "method": "mab", "device": "cam-front",
                          "vlan": "-", "mac": "02:aa:bb:cc:dd:01", "nas": "switch1", "reason": "device disabled"}],
                 "log_error": ""}
SAMPLE_DHCP = {"enabled": True, "interfaces": ["eth0"], "lease_time": 86400, "ddns_zone": "dhcp.home.arpa",
               "subnets": [{"subnet": "192.168.1.0/24", "id": 1, "name": "main", "vlan": 1,
                            "notes": "the house LAN", "pools": ["192.168.1.100 - 192.168.1.199"],
                            "routers": "192.168.1.1", "options": [{"name": "ntp-servers", "data": "192.168.1.2"}],
                            "reservations": [{"mac": "aa:bb:cc:00:11:22", "ip": "192.168.1.20",
                                              "hostname": "printer"}]}],
               "leases": [{"ip": "192.168.1.101", "mac": "02:11:22:33:44:55", "hostname": "laptop1.dhcp.home.arpa",
                           "expires": "2026-09-30T08:00", "state": "active", "subnet_id": 1}],
               "leases_error": "", "options": [{"name": "time-offset", "data": "-18000"}], "overrides": [],
               "option_defs": [], "client_classes": [{"name": "pxe-uefi", "test": "option[93].hex == 0x0007",
                                                      "next_server": "192.168.1.30", "boot_file_name": "ipxe.efi",
                                                      "options": [{"name": "tftp-server-name",
                                                                   "data": "192.168.1.30"}]}]}
SAMPLE = {
    "services": [("nginx", "active", "healthy"), ("bind9", "active", "healthy"), ("stepca", "active", "healthy"),
                 ("ldap", "active", "healthy"), ("postgres", "active", "healthy"), ("keycloak", "active", "healthy"),
                 ("openbao", "active", "healthy"), ("fabric-web", "active", "healthy"), ("fabric-agent", "active", "")],
    "host_changes": [
        {"group": g, "title": t, "state": st, "when": "2026-10-03T09:12:40+00:00" if st != "not asked" else "",
         "by": "admin" if st != "not asked" else "", "relaxation": r}
        for g, t, st, r in (
            ("packages", "Packages", "approved", ""), ("runtime", "Docker daemon settings", "approved", ""),
            ("services", "fabric's own services", "approved", ""), ("accounts", "Service accounts", "approved", ""),
            ("resolver", "Host DNS resolver", "not asked", ""), ("firewall", "Host firewall", "approved", ""),
            ("trust", "Host trust store", "declined", "this host does not trust fabric's CA: tools on the host (curl, "
                                                     "apt, browsers) reject fabric's certificates unless given the CA"),
            ("time", "Time service (chrony)", "approved", ""))],
    "zones": {
        "dynamic_zone_var": {"name": "home.arpa", "records": [
            ("A", "fabric", "192.168.1.53"), ("A", "@", "192.168.1.53"), ("A", "nas", "192.168.1.10"),
            ("CNAME", "ca", "fabric"), ("CNAME", "certs", "fabric"), ("CNAME", "dns", "fabric"),
            ("A", "printer", "192.168.1.40"), ("AAAA", "nas", "fd00:1:2:3::10"), ("A", "vpn", "203.0.113.7"),
            ("CNAME", "ca", "fabric"), ("CNAME", "certs", "fabric"), ("CNAME", "dns", "fabric"),
            ("CNAME", "sso", "fabric"), ("MX", "@", "10 mail"), ("TXT", "@", '"v=spf1 -all"')]},
        "iot.home.arpa": {"name": "iot.home.arpa", "records": [
            ("A", "cam-front", "192.168.20.11"), ("A", "cam-back", "192.168.20.12"), ("A", "thermostat",
                                                                                      "192.168.20.30")]},
    },
    "audit": ["[dev] User: dev (web) | Action: LOGIN | dev preview — no certificate, no Keycloak\n"],
    "tsig": [{"name": "npm-certbot", "algorithm": "hmac-sha256", "types": "TXT",
              "scope": "_acme-challenge.npm.home.arpa, _acme-challenge.nas.home.arpa", "acls": ["certbot-devices"]},
             {"name": "home.arpa-acme", "algorithm": "hmac-sha256", "types": "TXT",
              "scope": "_acme-challenge (zone home.arpa)", "acls": []}],
    "directory": {
        "roles": [{"name": "trusted", "description": "Managed laptops and phones", "priority": 10, "vlan": 10,
                   "permissions": ["dns:dhcp-register", "network:eap-tls", "pki:acme"], "members": ["jims-laptop",
                                                                                                    "jims-phone"]},
                  {"name": "iot", "description": "Cameras, plugs, thermostats", "priority": 50, "vlan": 30,
                   "permissions": ["dns:dhcp-register", "network:mab"], "members": ["cam-front", "thermostat"]},
                  {"name": "printers", "description": "", "priority": 60, "vlan": None,
                   "permissions": ["network:mab", "pki:scep"], "members": ["printer"]},
                  {"name": "quarantine", "description": "No access; parked devices", "priority": 1, "vlan": 99,
                   "permissions": [], "members": []}],
        "devices": [{"name": "jims-laptop", "type": "laptop", "enabled": True, "macs": ["3c:22:fb:10:20:30"],
                     "owner": "uid=jim,ou=users", "description": "ThinkPad", "certs": [":".join(["AB"] * 32)]},
                    {"name": "jims-phone", "type": "phone", "enabled": True, "macs": ["f2:11:22:33:44:55"],
                     "owner": "uid=jim,ou=users", "description": "", "certs": []},
                    {"name": "cam-front", "type": "camera", "enabled": True, "macs": ["b0:a7:32:00:00:11"],
                     "owner": "", "description": "Front door", "certs": []},
                    {"name": "thermostat", "type": "iot", "enabled": False, "macs": ["18:b4:30:aa:bb:cc"],
                     "owner": "", "description": "Disabled: firmware out of date", "certs": []},
                    {"name": "printer", "type": "printer", "enabled": True, "macs": ["00:1b:a9:12:34:56"],
                     "owner": "", "description": "Office laser", "certs": []}]},
    "people": {"users": [{"uid": "jim", "name": "Jim", "mail": "jim@home.arpa", "locked": False, "groups": ["admins",
                                                                                                            "users"]},
                         {"uid": "sam", "name": "Sam", "mail": "sam@home.arpa", "locked": False, "groups": ["users"]}],
               "groups": [{"name": "admins", "members": 1}, {"name": "users", "members": 2}],
               "keycloak_url": "https://sso.home.arpa/admin/home.arpa/console/"},
    "issued": [{"when": "2026-09-20T10:12:00", "actor": "dev", "kind": "csr", "subject": "CN=switch-core.home.arpa",
                "sans": ["switch-core.home.arpa", "192.168.1.2"], "not_after": "Sep 20 10:12:00 2027 GMT",
                "status": "valid"},
               {"when": "2025-10-01T08:00:00", "actor": "dev", "kind": "keypair", "subject": "CN=printer.home.arpa",
                "sans": ["printer.home.arpa"], "not_after": "Oct 15 08:00:00 2026 GMT", "status": "expires soon"}],
}
_FP = ":".join(["AB", "12", "CD", "34"] * 8)
SAMPLE_VAULT = {"url": "https://vault.home.arpa/", "reachable": True, "initialized": True, "sealed": False,
                "version": "2.7.0", "seal_type": "static", "storage": "raft", "recovery_seal": True,
                "key": {"path": "/etc/fabric/openbao/unseal.key", "present": True, "ok": True,
                        "detail": "32 bytes, 0400, openbao only"},
                "mounts": [{"path": "apps/", "type": "kv", "version": "2",
                            "description": "secrets for your applications"},
                           {"path": "cubbyhole/", "type": "cubbyhole", "version": None,
                            "description": "per-token private secret storage"},
                           {"path": "fabric/", "type": "kv", "version": "2", "description": "fabric's own secrets"},
                           {"path": "identity/", "type": "identity", "version": None, "description": "identity store"},
                           {"path": "sys/", "type": "system", "version": None, "description": "system endpoints"}],
                "auth": ["approle/", "oidc/", "token/"], "secrets": {"version": 7, "updated": "2026-09-29T09:12:44"}}
SAMPLE_SLOTS = [
    {"id": "local", "type": "local", "label": "Key file on this host", "device": "/etc/fabric/openbao/unseal.key",
     "present": True, "key_id": "fabric-1", "added": "2026-09-28",
     "detail": "always present: while this slot exists, removing a device cannot seal the vault"},
    {"id": "s-yk1", "type": "security-key", "label": "Pi key", "device": "YubiKey 5 Nano · serial 23456781 · key 03",
     "present": True, "key_id": "fabric-1", "added": "2026-09-29",
     "detail": "the key cannot be copied; its PIN is kept root-only on this host"}]
SAMPLE_DEVICES = {"tokens": [{"vendor": "Yubico", "product": "YubiKey OTP+FIDO+CCID", "serial": "23456781",
                              "usb_id": "1050:0407", "port": "1-1.2"},
                             {"vendor": "Yubico", "product": "YubiKey OTP+FIDO+CCID", "serial": "23456799",
                              "usb_id": "1050:0407", "port": "1-1.3"}],
                  "disks": [{"path": "/dev/sda", "model": "SanDisk Ultra Fit", "serial": "4C530001230912104582",
                             "size_gb": 32.0, "uuids": ["9A1C-33F0"], "labels": ["USB"]}],
                  "pkcs11": [{"module": "/usr/lib/aarch64-linux-gnu/libykcs11.so.2", "library": "libykcs11.so.2",
                              "serial": "23456781", "label": "YubiKey PIV #23456781",
                              "manufacturer": "Yubico (www.yubico.com)",
                              "model": "YubiKey YK5", "pin_state": "ok"},
                             {"module": "/usr/lib/aarch64-linux-gnu/libykcs11.so.2", "library": "libykcs11.so.2",
                              "serial": "23456799", "label": "YubiKey PIV #23456799",
                              "manufacturer": "Yubico (www.yubico.com)",
                              "model": "YubiKey YK5", "pin_state": "ok"}]}
SAMPLE_CA = {"domain": "home.arpa", "certs_url": "http://certs.home.arpa/", "max_days": 1825,
             "root": {"subject": "CN=Fabric Root CA,O=Fabric", "not_after": "Sep  1 00:00:00 2046 GMT",
                      "key": "EC prime256v1", "sha256": _FP},
             "intermediate": {"subject": "CN=Fabric Intermediate CA,O=Fabric", "not_after": "Sep  1 00:00:00 2036 GMT",
                              "key": "EC prime256v1", "sha256": _FP}}
SAMPLE_PEM = "-----BEGIN CERTIFICATE-----\nDEV PREVIEW — sample, not a real certificate\n-----END CERTIFICATE-----\n"
# decodes (the Windows scripts hash it) but is no certificate: the preview's scripts are samples only
SAMPLE_ROOT_PEM = ("-----BEGIN CERTIFICATE-----\nREVWIFBSRVZJRVcgc2FtcGxlIHJvb3QgQ0EgLSBub3QgYSByZWFsIGNlcnRpZmljYXRl\n"
                   "-----END CERTIFICATE-----\n")
SAMPLE_KEY = "-----BEGIN PRIVATE KEY-----\nDEV PREVIEW — sample, not a real key\n-----END PRIVATE KEY-----\n"
SAMPLE_INFO = {"subject": "CN=device.home.arpa,OU=IT,O=Fabric", "issuer": "CN=Fabric Intermediate CA,O=Fabric",
               "sans": ["device.home.arpa", "192.168.1.50"], "key": "RSA 2048", "serial": "0x1A2B3C4D5E",
               "not_before": "Sep 28 00:00:00 2026 GMT", "not_after": "Sep 28 00:00:00 2027 GMT", "sha256": _FP,
               "usage": "TLS Web Server Authentication, TLS Web Client Authentication", "is_ca": False}
