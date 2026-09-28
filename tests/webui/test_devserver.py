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
    check("dashboard renders with the DEV PREVIEW banner", st == 200 and "DEV PREVIEW" in page and "DNS zones" in page, st)
    check("strict Content-Security-Policy, like production", csp and "default-src 'none'" in csp, csp)
    st, _, _, page = req("GET", "/zone/dynamic_zone_var")
    check("zone page renders sample records", st == 200 and "nas" in page and "192.168.1.10" in page, st)
    st, loc, _, _ = req("POST", "/zone/dynamic_zone_var/add", {"type": "A", "name": "preview", "ip": "192.168.1.99", "csrf": "dev"})
    st2, _, _, page = req("GET", "/zone/dynamic_zone_var")
    check("adding a record works (in memory)", st == 303 and "192.168.1.99" in page, (st, loc))
    idx = re.search(r'name="index" value="(\d+)"><input type="hidden" name="name" value="preview"', page)
    req("POST", "/zone/dynamic_zone_var/delete", {"type": "A", "index": idx.group(1) if idx else "-1", "name": "preview"})
    st, _, _, page = req("GET", "/zone/dynamic_zone_var")
    check("deleting a record works (in memory)", "192.168.1.99" not in page)
    st, _, _, page = req("POST", "/apply", {"csrf": "dev"})
    check("apply is a no-op that says so", st == 200 and "nothing was rendered or reloaded" in page)
    st, _, _, page = req("GET", "/audit")
    check("audit log shows the preview's actions", "DNS_ADD" in page and "in memory" in page)
    st, _, _, page = req("GET", "/preview/denied")
    check("preview of a refused sign-in", st == 403 and "fabric-admin" in page)
finally:
    proc.terminate()
    proc.wait(timeout=5)

prod = views.dashboard({"user": "u", "csrf": "x", "version": {"version": "1", "build": ""}}, [], [])
check("production pages never show the banner", "DEV PREVIEW" not in prod)
src = open(os.path.join(LIB, "webui", "server.py")).read()
check("the production server has no dev switch", "devserver" not in src and '"dev"' not in src and "DEV" not in src)
check("dev server listens on 127.0.0.1 unless told otherwise",
      'default="127.0.0.1"' in open(os.path.join(LIB, "webui", "devserver.py")).read())
sys.exit(1 if FAILED else 0)
