#!/usr/bin/env python3
"""The web UI dev preview: real pages with sample data, edits in memory only,
and no way to switch it on in the production server."""
import http.client
import os
import re
import subprocess
import sys
import time
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(REPO, "fabric", "lib")
sys.path.insert(0, LIB)
from webui import views  # noqa: E402

PORT = 18765
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:300]}"))


def req(method, path, form=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    body = urllib.parse.urlencode(form) if form is not None else None
    c.request(method, path, body=body, headers={"Content-Type": "application/x-www-form-urlencoded"} if body else {})
    r = c.getresponse()
    data = r.read().decode()
    return r.status, r.getheader("Location"), r.getheader("Content-Security-Policy"), data


proc = subprocess.Popen([sys.executable, os.path.join(LIB, "webui", "devserver.py"), "--port", str(PORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    for _ in range(50):
        try:
            req("GET", "/static/app.css")
            break
        except OSError:
            time.sleep(0.1)
    st, _, csp, page = req("GET", "/")
    check("overview renders with the DEV PREVIEW banner", st == 200 and "DEV PREVIEW" in page and "services healthy" in page, st)
    tabs_ok = all(req("GET", f"/{t}")[3].count("Left intentionally blank") == 1 for t in ("kea", "freeradius"))
    check("every service tab renders (placeholders)", tabs_ok)
    check("strict Content-Security-Policy, like production", csp and "default-src 'none'" in csp, csp)
    st, _, _, page = req("GET", "/bind9?zone=dynamic_zone_var")
    check("BIND9 tab shows records and the add form", st == 200 and "nas" in page and "192.168.1.10" in page, st)
    st, loc, _, _ = req("POST", "/bind9/zone/dynamic_zone_var/add", {"type": "A", "name": "preview", "ip": "192.168.1.99", "csrf": "dev"})
    st2, _, _, page = req("GET", "/bind9?zone=dynamic_zone_var")
    check("adding a record works (in memory)", st == 303 and "192.168.1.99" in page, (st, loc))
    idx = re.search(r'name="index" value="(\d+)"><input type="hidden" name="name" value="preview"', page)
    req("POST", "/bind9/zone/dynamic_zone_var/delete", {"type": "A", "index": idx.group(1) if idx else "-1", "name": "preview"})
    st, _, _, page = req("GET", "/bind9?zone=dynamic_zone_var")
    check("deleting a record works (in memory)", "192.168.1.99" not in page)
    st, _, _, page = req("POST", "/apply", {"csrf": "dev"})
    check("apply is a no-op that says so", st == 200 and "nothing was rendered or reloaded" in page)
    st, _, _, page = req("GET", "/audit")
    check("audit log shows the preview's actions", "DNS_ADD" in page and "in memory" in page)
    pages = [req("GET", f"/stepca?view={v}") for v in ("ca", "sign", "issue", "inspect", "convert", "issued")]
    check("every Step-CA menu page renders", all(p[0] == 200 for p in pages) and "Fabric Root CA" in pages[0][3]
          and "switch-core.home.arpa" in pages[5][3])
    st, _, _, page = req("POST", "/stepca/issue", {"csrf": "dev", "cn": "x"})
    check("generate shows sample downloads and the one-time key warning",
          st == 200 and 'download="device.home.arpa.key"' in page and "only copy of the private key" in page)
    page = req("GET", "/")[3]
    check("overview shows one status light per service", page.count('class="light ok"') == 9 and "pill" not in page.split("<section class=\"tiles\">")[1])
    st, _, _, page = req("GET", "/bind9?view=reverse")
    check("reverse zones generated from forward A/AAAA records",
          st == 200 and "1.168.192.in-addr.arpa" in page and "20.168.192.in-addr.arpa" in page
          and "cam-front.iot.home.arpa." in page and ".ip6.arpa" in page, page[:300])
    check("public address listed without a reverse record", "203.0.113.7" in page and "public address" in page)
    st, _, _, page = req("GET", "/bind9?zone=dynamic_zone_var")
    check("forward records show their automatic PTR", "40.1.168.192.in-addr.arpa" in page)
    st, _, _, page = req("GET", "/bind9?view=tsig")
    check("TSIG view lists sample keys", st == 200 and "npm-certbot" in page and "New TSIG key for a zone" in page)
    st, _, _, page = req("POST", "/bind9/tsig/create", {"csrf": "dev", "name": "preview-key", "zone": "home.arpa"})
    check("creating a TSIG key shows its secret and rfc2136.ini once",
          st == 200 and "dns_rfc2136_name = preview-key" in page and 'class="secret"' in page)
    st, _, _, page = req("GET", "/dirsrv")
    check("389-DS devices page: devices with status lights, roles and access",
          st == 200 and "jims-laptop" in page and "VLAN 10" in page and 'class="light bad"' in page)
    st, _, _, page = req("GET", "/dirsrv?view=device&name=jims-laptop")
    check("device page: effective permissions and linked certificate",
          "Join the network with its certificate" in page and "AB:AB:AB" in page and "Generate key + certificate" in page)
    st, loc, _, _ = req("POST", "/dirsrv/devices/_new", {"csrf": "dev", "name": "nas", "type": "server",
                                                         "macs": "AA-BB-CC-00-00-01", "role_trusted": "1", "enabled": "1"})
    page = req("GET", "/dirsrv?view=device&name=nas")[3]
    check("adding a device (in memory, real validation): MAC normalised, role applied",
          st == 303 and "aa:bb:cc:00:00:01" in page and "VLAN" in page, (st, loc))
    st, loc, _, _ = req("POST", "/dirsrv/devices/_new", {"csrf": "dev", "name": "dup", "macs": "aa:bb:cc:00:00:01"})
    check("a MAC already in use is refused with the reason", "already+belongs" in (loc or "") or "already%20belongs" in (loc or ""), loc)
    st, loc, _, _ = req("POST", "/dirsrv/roles/iot/delete", {"csrf": "dev"})
    check("a role that still has devices cannot be deleted", "still+has" in (loc or ""), loc)
    page = req("GET", "/dirsrv?view=roles")[3]
    check("roles page lists roles with their grants", "quarantine" in page and "network:mab" in page)
    page = req("GET", "/dirsrv?view=people")[3]
    check("people page (admin): people, add form, reset buttons, Keycloak link for fabric groups",
          "jim@home.arpa" in page and "Keycloak admin console" in page and "/dirsrv/people/_new" in page
          and "Reset sign-in" in page)
    page = req("GET", "/stepca?view=issue&device=printer")[3]
    check("Step-CA generate form offers devices, prefilled from the device page",
          "<option selected>printer</option>" in page and 'value="printer.home.arpa"' in page)
    page = req("GET", "/openbao")[3]
    check("OpenBao tab: unsealed, static seal, engines", "Unsealed" in page and "static" in page and "fabric/" in page)
    page = req("GET", "/openbao?view=secrets")[3]
    check("secrets: fabric's own entry, OpenBao UI link (OIDC), break glass", "fabric/secrets" in page
          and "ui/vault/auth?with=oidc" in page and "break-glass" in page)
    page = req("GET", "/openbao?view=unlock")[3]
    check("unlock methods: slots, kill-switch state, the key-file warning", "Kill switch off" in page
          and "YubiKey 5 Nano" in page and "Remove the key file" in page)
    page = req("GET", "/openbao?view=add-security-key")[3]
    check("add security key: PKCS#11 tokens, enrolled one disabled, untested-hardware note", "23456799" in page
          and "already an unlock method" in page and 'name="pin"' in page and "untested" in page
          and 'value="/usr/lib/aarch64-linux-gnu/libykcs11.so.2|23456799"' in page)
    st, loc, _, _ = req("POST", "/openbao/slots/add-security-key", {"csrf": "dev", "token": "/usr/lib/aarch64-linux-gnu/libykcs11.so.2|23456799", "pin": "x",
                                                                    "label": "safe key", "confirm": "wrong"})
    check("vault changes need the host name typed", "confirm" in (loc or ""), loc)
    req("POST", "/openbao/slots/add-security-key", {"csrf": "dev", "token": "/usr/lib/aarch64-linux-gnu/libykcs11.so.2|23456799", "pin": "x", "label": "safe key",
                                                    "confirm": "pi-core"})
    req("POST", "/openbao/slots/local/remove", {"csrf": "dev", "confirm": "pi-core"})
    page = req("GET", "/openbao?view=unlock")[3]
    check("add a second key, remove the key file: kill switch armed", "safe key" in page and "Kill switch armed" in page
          and "/etc/fabric/openbao/unseal.key" not in page)
    st, loc, _, _ = req("POST", "/openbao/rotate", {"csrf": "dev", "confirm": "pi-core"})
    check("rotate: new key version on every present method", "fabric-2" in req("GET", "/openbao?view=unlock")[3])
    st, _, _, page = req("GET", "/preview/denied")
    check("preview of a refused sign-in", st == 403 and "fabric-admin" in page)
finally:
    proc.terminate()
    proc.wait(timeout=5)

PORT += 1                                   # people: the helpdesk bundle
proc = subprocess.Popen([sys.executable, os.path.join(LIB, "webui", "devserver.py"), "--port", str(PORT),
                         "--as", "fabric-helpdesk"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    for _ in range(50):
        try:
            req("GET", "/")
            break
        except OSError:
            time.sleep(0.2)
    page = req("GET", "/dirsrv?view=people")[3]
    check("helpdesk: add form and reset buttons", "/dirsrv/people/_new" in page and "Reset sign-in" in page)
    st, _, _, page = req("POST", "/dirsrv/people/_new", {"csrf": "dev", "uid": "dana", "first": "Dana", "last": "Lee",
                                                         "email": "dana@home.arpa"})
    check("helpdesk: add a person -> one-time password shown once", st == 200 and "shown only now" in page and "dana" in page)
    st, _, _, page = req("POST", "/dirsrv/people/sam/reset", {"csrf": "dev"})
    check("helpdesk: reset a plain user's sign-in", st == 200 and "sign-in reset" in page)
    st, loc, _, _ = req("POST", "/dirsrv/people/jim/reset", {"csrf": "dev"})
    check("helpdesk: an admin's sign-in cannot be reset", st == 303 and "only%20an%20admin" in (loc or ""), loc)
finally:
    proc.terminate()
    proc.wait(timeout=5)

PORT += 1                                   # the preview as a role bundle sees it
proc = subprocess.Popen([sys.executable, os.path.join(LIB, "webui", "devserver.py"), "--port", str(PORT),
                         "--as", "fabric-auditor"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    for _ in range(50):
        try:
            req("GET", "/")
            break
        except OSError:
            time.sleep(0.2)
    page = req("GET", "/bind9")[3]
    check("--as fabric-auditor: records shown, no add form", "nas" in page and "/add" not in page and "as fabric-auditor" in page)
    page = req("GET", "/dirsrv?view=people")[3]
    check("--as fabric-auditor: people listed, no add form or reset buttons",
          "jim@home.arpa" in page and "/dirsrv/people/_new" not in page and "Reset sign-in" not in page)
finally:
    proc.terminate()
    proc.wait(timeout=5)

prod = views.overview({"user": "u", "csrf": "x", "version": {"version": "1", "build": ""}}, [])
check("production pages never show the banner", "DEV PREVIEW" not in prod)
src = open(os.path.join(LIB, "webui", "server.py")).read()
check("the production server has no dev switch", "devserver" not in src and '"dev"' not in src and "DEV" not in src)
check("dev server listens on 127.0.0.1 unless told otherwise",
      'default="127.0.0.1"' in open(os.path.join(LIB, "webui", "devserver.py")).read())
sys.exit(1 if FAILED else 0)
