#!/usr/bin/env python3
"""The DNS filter tab (manual 1.12.2.14) without a host: the settings it changes (lists, rules, upstreams) on an
in-memory vars file, fabric-agent's routes and their permissions, the lists job's apply when a list is new, the web
UI's post route and the page for each kind of user. What must be refused is checked beside what must be accepted.

    python3 tests/resolver/console.py
"""
import contextlib
import copy
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[0:0] = [os.path.join(REPO, "src")]
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))


def refused(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except Exception as e:  # noqa: BLE001 — the test reads the refusal's type and text
        return e
    return None


from fabriclib.common.errors import ValidationError  # noqa: E402
import fabriclib.dns_filter.add_filter_list as m_add_list  # noqa: E402
import fabriclib.dns_filter.add_filter_rule as m_add_rule  # noqa: E402
import fabriclib.dns_filter.remove_filter_list as m_rm_list  # noqa: E402
import fabriclib.dns_filter.remove_filter_rule as m_rm_rule  # noqa: E402
import fabriclib.dns_filter.set_filter_upstreams as m_ups  # noqa: E402
import fabriclib.dns_filter.refresh_lists as m_refresh  # noqa: E402
from fabriclib.dns_filter.common.list_zone import list_zone  # noqa: E402
from fabriclib.rbac.permissions import BUNDLES  # noqa: E402
from fabriclib.rbac.required_permission import required_permission  # noqa: E402

L1 = "https://lists.example/one.txt"
STORE = {"vars": {"domain": "lan.test", "org_domain": "lan.test", "dns_filter": "bind", "install_resolver": True,
                  "dns_filter_lists": [{"name": "One", "url": L1}], "dns_filter_allow": [], "dns_filter_block": [],
                  "dns_filter_upstreams": [{"address": "1.1.1.1", "name": "cloudflare-dns.com"}]}}
AUDIT = []
for mod in (m_add_list, m_add_rule, m_rm_list, m_rm_rule, m_ups):
    mod.load_vars = lambda: copy.deepcopy(STORE["vars"])
    mod.save_vars = lambda data: STORE.update(vars=copy.deepcopy(data))
    mod.vars_lock = contextlib.nullcontext
    mod.write_audit = lambda actor, action, detail, source: AUDIT.append((actor, action, detail, source))
v = lambda: STORE["vars"]  # noqa: E731

# ---- lists
r = m_add_list.add_filter_list("alice", "Two", "https://lists.example/two.txt", "web")
check("add a list: saved after the others, its zone named from its URL, audited",
      [i["name"] for i in v()["dns_filter_lists"]] == ["One", "Two"] and r["zone"] == list_zone(
          "https://lists.example/two.txt") and AUDIT[-1][:2] == ("alice", "DNS_FILTER_LIST_ADD"), (r, AUDIT[-1:]))
before = copy.deepcopy(STORE["vars"])
for args, why in ((("x", "ftp://lists.example/x"), "not http(s)"), (("x", L1), "the same URL twice"),
                  (("y" * 201, "https://lists.example/y"), "a name over 200 characters")):
    e = refused(m_add_list.add_filter_list, "alice", *args)
    check(f"add a list refused: {why}, saying why, nothing saved",
          isinstance(e, ValidationError) and str(e) and STORE["vars"] == before, e)
m_rm_list.remove_filter_list("alice", "https://lists.example/two.txt", "web")
check("remove a list", [i["url"] for i in v()["dns_filter_lists"]] == [L1])
e = refused(m_rm_list.remove_filter_list, "alice", "https://lists.example/nope.txt")
check("remove a list refused: not there", isinstance(e, ValidationError) and "no list" in str(e), e)

# ---- rules
r = m_add_rule.add_filter_rule("alice", "block", "Ads.Example.org.", "web")
check("block a name: normalised (lowercase, no trailing dot), audited",
      v()["dns_filter_block"] == ["ads.example.org"] and r == {"kind": "block", "name": "ads.example.org",
                                                               "moved": False} and AUDIT[-1][1] == "DNS_FILTER_BLOCK", r)
r = m_add_rule.add_filter_rule("alice", "allow", "ads.example.org", "web")
check("allowing a blocked name moves it (Allow pressed in the query log)",
      v()["dns_filter_allow"] == ["ads.example.org"] and v()["dns_filter_block"] == [] and r["moved"], r)
m_add_rule.add_filter_rule("alice", "allow", "ads.example.org", "web")
check("allowing it again changes nothing (no duplicate)", v()["dns_filter_allow"] == ["ads.example.org"])
before = copy.deepcopy(STORE["vars"])
for args, why in ((("deny", "x.example"), "another kind"), (("block", "not a name!"), "not a name"),
                  (("block", "nas.lan.test"), "a name inside fabric's own domain")):
    e = refused(m_add_rule.add_filter_rule, "alice", *args)
    check(f"rule refused: {why}, saying why, nothing saved",
          isinstance(e, ValidationError) and str(e) and STORE["vars"] == before, e)
m_rm_rule.remove_filter_rule("alice", "allow", "ADS.example.org", "web")
check("remove a rule (as listed, any case)", v()["dns_filter_allow"] == [])
e = refused(m_rm_rule.remove_filter_rule, "alice", "block", "never.example")
check("remove a rule refused: not in that rule", isinstance(e, ValidationError) and "not blocked" in str(e), e)

# ---- upstreams
r = m_ups.set_filter_upstreams("alice", "9.9.9.9 dns.quad9.net\n149.112.112.112 DNS.quad9.net", "web")
check("upstreams: address and certificate-name pairs, one per line or comma-separated",
      v()["dns_filter_upstreams"] == [{"address": "9.9.9.9", "name": "dns.quad9.net"},
                                      {"address": "149.112.112.112", "name": "dns.quad9.net"}], r)
check("upstreams: none is the root servers", m_ups.set_filter_upstreams("alice", "None") == []
      and v()["dns_filter_upstreams"] == [])
before = copy.deepcopy(STORE["vars"])
for text, why in (("", "empty"), ("9.9.9.9", "an address without its certificate name"),
                  ("dns.quad9.net 9.9.9.9", "the two the wrong way round")):
    e = refused(m_ups.set_filter_upstreams, "alice", text)
    check(f"upstreams refused: {why}, saying why, nothing saved",
          isinstance(e, ValidationError) and str(e) and STORE["vars"] == before, e)

# ---- fabric-agent's routes and their permissions
routes = {("GET", ("dns-filter",)): "dns:filter", ("POST", ("dns-filter", "querylog")): "dns:querylog"}
routes.update({("POST", ("dns-filter", *p)): "dns:filter"
               for p in (("lists",), ("lists", "delete"), ("rules",), ("rules", "delete"), ("upstreams",), ("fetch",))})
check("every route needs its permission: the query log dns:querylog, the rest dns:filter",
      all(required_permission(m, list(p)) == need for (m, p), need in routes.items()))
check("refused: a DNS filter route not listed (default deny)",
      required_permission("POST", ["dns-filter", "lists", "rename"]) is None
      and required_permission("GET", ["dns-filter", "querylog"]) is None)
check("network operators manage the filter but cannot read the query log; auditors neither",
      "dns:filter" in BUNDLES["fabric-network-operator"] and "dns:querylog" not in BUNDLES["fabric-network-operator"]
      and not {"dns:filter", "dns:querylog"} & set(BUNDLES["fabric-auditor"]))

import agent.post_dns_filter as pdf  # noqa: E402
from agent.route_not_found import RouteNotFound  # noqa: E402
CALLS = []
pdf.apply_changes = lambda actor, source: (CALLS.append(("apply", actor, source)) or (True, "applied"))
pdf.start_list_fetch = lambda: (CALLS.append(("fetch",)) or True)
pdf.add_filter_list = m_add_list.add_filter_list
pdf.load_vars = lambda: STORE["vars"]
pdf.read_query_log = lambda vv, **kw: (CALLS.append(("querylog", kw)) or {"entries": []})
r = pdf.post_dns_filter(["dns-filter", "lists"], "alice", {"name": "Three", "url": "https://lists.example/3.txt"})
check("agent: adding a list saves it, applies, and starts the lists job (fabric-agent has no internet)",
      r["applied"] and r["fetching"] and CALLS[-2:] == [("apply", "alice", "web"), ("fetch",)], (r, CALLS))
CALLS.clear()
e = refused(pdf.post_dns_filter, ["dns-filter", "lists"], "alice", {"url": "ftp://x"})
check("agent: a refused change is a 400 (ValidationError) and nothing is applied or fetched",
      isinstance(e, ValidationError) and CALLS == [], (e, CALLS))
e = refused(pdf.post_dns_filter, ["dns-filter", "lists"], "alice", {"url": 42})
check("agent: a field that is not text is refused", isinstance(e, ValidationError) and "text" in str(e), e)
check("agent: an unknown DNS filter route is a 404", isinstance(refused(pdf.post_dns_filter, ["dns-filter", "x"],
                                                                         "alice", {}), RouteNotFound))
r = pdf.post_dns_filter(["dns-filter", "querylog"], "alice", {"client": "192.168.1.0/24", "blocked": True, "limit": 50})
check("agent: the query-log search passes its terms on", CALLS[-1] == ("querylog", {
    "client": "192.168.1.0/24", "name": "", "blocked_only": True, "limit": 50}), CALLS[-1:])

# ---- the lists job applies once a list has a copy the running configuration does not name yet
with tempfile.TemporaryDirectory() as tmp:
    vv = {"deploy_base_dir": tmp, "dns_filter_lists": [{"name": "One", "url": L1}]}
    os.makedirs(f"{tmp}/resolver/config")
    os.makedirs(f"{tmp}/resolver/lists")
    open(f"{tmp}/resolver/lists/{list_zone(L1)}", "w").write("x")
    m_refresh.update_lists = lambda vv: {"changed": [], "failed": [], "lists": {}}
    m_refresh.fetch_catalogue = lambda vv: {"lists": [1, 2, 3]}
    APPLIED = []
    m_refresh.apply_changes = lambda actor, source: (APPLIED.append(source) or (True, ""))
    open(f"{tmp}/resolver/config/named.conf", "w").write('zone "fabric.rpz" {};\n')
    r = m_refresh.refresh_lists(vv, source="timer")
    check("lists job: a fetched list not in the running configuration is applied", r["applied"] is True
          and APPLIED == ["timer"] and r["catalogue"] == 3, r)
    open(f"{tmp}/resolver/config/named.conf", "w").write(f'zone "{list_zone(L1)}" {{}};\n')
    APPLIED.clear()
    r = m_refresh.refresh_lists(vv)
    check("lists job: nothing to apply when every list is in use", r["applied"] is None and APPLIED == [], r)
    m_refresh.fetch_catalogue = lambda vv: (_ for _ in ()).throw(OSError("offline"))
    check("lists job: the catalogue unreachable keeps the last copy (None), the job goes on",
          m_refresh.refresh_lists(vv)["catalogue"] is None)

# ---- the web UI: its post route and the page for each kind of user
from webui import views  # noqa: E402
import webui.routes.dns_filter_post as wpost  # noqa: E402


class H:
    def __init__(self):
        self.out = None

    def redirect(self, location, headers=None):
        self.out = (303, location)

    def deny(self, status, text):
        self.out = (status, text)


class FakeActions:
    ValidationError = ValidationError

    def __init__(self, applied=True, refuse=None):
        self.applied, self.refuse, self.calls = applied, refuse, []

    def dns_filter_change(self, what, body):
        self.calls.append((what, body))
        if self.refuse:
            raise ValidationError(self.refuse)
        result = [{"address": "9.9.9.9", "name": "dns.quad9.net"}] if what == "upstreams" else \
            {"name": body.get("name"), "kind": body.get("kind")}          # the agent's shapes
        return {"result": result, "applied": self.applied, "output": "boom" * 100, "fetching": True}


h, wpost.actions = H(), FakeActions()
wpost.dns_filter_post(h, ["rules"], {"kind": "block", "name": "x.example", "back": "querylog"})
check("web: Block from the query log saves and goes back to the query log with the outcome",
      h.out[0] == 303 and h.out[1].startswith("/dns-filter?view=querylog&msg=") and wpost.actions.calls[-1][0] == "rules",
      h.out)
wpost.dns_filter_post(h, ["lists"], {"name": "Two", "url": "https://x/2", "back": "<script>"})
check("web: a back section that is not one is ignored (the change's own section)",
      h.out[1].startswith("/dns-filter?view=lists&msg="), h.out)
h, wpost.actions = H(), FakeActions(refuse="not a DNS name")
wpost.dns_filter_post(h, ["rules"], {"kind": "block", "name": "bad!"})
check("web: a refused change goes back with the reason (err)", "err=not+a+DNS+name" in h.out[1], h.out)
h, wpost.actions = H(), FakeActions(applied=False)
wpost.dns_filter_post(h, ["upstreams"], {"upstreams": "9.9.9.9 dns.quad9.net"})
check("web: saved but not applied says so, with the apply's output's end",
      "applying+failed" in h.out[1] and "view=settings" in h.out[1], h.out)
h = H()
wpost.dns_filter_post(h, ["lists", "rename"], {})
check("web: an unknown change is a 404", h.out[0] == 404, h.out)

OV = {"on": True, "lists": [], "allow": ["a.example"], "block": [], "upstreams": [], "memory_limit": "384m",
      "stats": {"off": "Postgres is not installed"}, "catalogue": {"fetched": None, "lists": []}}
LOG = {"entries": [{"at": "2026-10-09T10:00:00Z", "client": "192.168.1.2", "view": "everyone", "name": "ads.example",
                    "qtype": "A", "action": "NXDOMAIN", "zone": "owner.rpz", "list": None, "blocked": True}]}
SEARCH = {"client": "", "name": "", "blocked": "", "limit": ""}


def ctx(*perms):
    return {"perms": list(perms), "csrf": "t", "user": "alice", "dev": False,
            "version": {"version": "test", "build": ""}}


admin = views.dns_filter(ctx("dns:filter", "dns:querylog"), "querylog", OV, LOG, SEARCH)
operator = views.dns_filter(ctx("dns:filter"), "rules", OV, None, SEARCH)
reader = views.dns_filter(ctx("dns:querylog"), "querylog", None, LOG, SEARCH)
check("page: the admin sees the query log with Allow on a blocked line, and the DNS filter tab",
      "ads.example" in admin and 'action="/dns-filter/rules"' in admin and 'href="/dns-filter"' in admin)
check("page: a network operator gets the rules' forms but no Query log section",
      'action="/dns-filter/rules"' in operator and "?view=querylog" not in operator)
check("page: with dns:querylog only, the log shows without any form that changes the filter",
      "ads.example" in reader and "/dns-filter/rules" not in reader and "/dns-filter/lists" not in reader)
check("page: statistics off says why", "Postgres is not installed" in views.dns_filter(
    ctx("dns:filter"), "overview", OV, None, SEARCH))

print("\nall passed (0 failures)" if not FAILED else f"\n{FAILED} failed")
sys.exit(1 if FAILED else 0)
